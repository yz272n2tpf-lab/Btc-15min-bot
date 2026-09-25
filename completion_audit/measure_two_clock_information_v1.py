"""Synthetic source-qualified availability with real frozen inference timings.

No model fitting, outcomes, September cohort, predictions scored, or live I/O.
Both timelines use the same timestamped source events and native action ticks.
The source delay is an engineering scenario parameter, never a model parameter.
"""
import json
from pathlib import Path
import statistics
import time
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from btc15_information_v1 import FairAssessment, InformationPublisher, unpack, validate
from completion_audit.isolated_decision_v2 import FrozenRuntime
from test_btc15_information_v1 import Rig
from test_btc15_isolated_decision_v2 import completed, OPEN, fixture


def run(name, initial, model, delay=2.486, outage=None, duration=30):
    start=time.perf_counter();rig=Rig(initial,brti_delay=delay)
    first_native=time.perf_counter()-start
    pub=InformationPublisher(model,retention=128)
    frames=[];native=[];health_events=[];inference=[];export_cost=[]
    for second in range(duration):
        cut=300+second
        failed=outage is not None and outage[0]<=second<outage[1]
        native_cost=0.
        if second%5==0:
            before=time.perf_counter()
            if second:
                inp,_=rig.tick(cut,brti_delay=delay,quote_wait=failed)
            else:
                inp=fixture(cut,brti_delay=delay)
            native_cost=(time.perf_counter()-before) if second else first_native
            if not failed:
                # Actual native complete-decision cost is measured locally.
                native.append(dict(published=OPEN+cut+native_cost,
                    expires=inp['brti_receipts'][0][1]+5,cut=OPEN+cut))
        else:
            rig.sources(cut,brti_delay=delay)
        rig.at=OPEN+cut+native_cost
        if failed:
            rig.provider.book.valid=False
            pub.unavailable('SYNTHETIC_QUOTE_INTERRUPTION')
            health_events.append((rig.at,None))
            continue
        try:
            health=rig.export.health()
            health_events.append((rig.at,health))
            rig.at+=.25  # Worst polling phase of the implemented 250 ms worker.
            begin=time.perf_counter();raw=rig.export.capture()
            capture_cost=time.perf_counter()-begin
            export_cost.append(capture_cost)
            rig.at+=capture_cost
            begin=time.perf_counter()
            # Inference and two health reads are measured, not treated as instant.
            def clock():return rig.at+time.perf_counter()-begin
            if pub.offer(raw,rig.export.health,clock):
                saved=pub.frames[pub.latest]
                out=unpack(saved[1]);inference.append(out['published_ts']-rig.at)
                frames.append((out['published_ts'],saved[0],out))
        except ValueError:
            health_events.append((rig.at,None))
    # Fixed 10 ms observation grid; zero lookahead. Latest completed publication
    # and latest observed health only; missing/wait is counted in denominator.
    info_ok=action_ok=0;count=duration*100
    for i in range(count):
        now=OPEN+300+i/100
        hs=[h for t,h in health_events if t<=now]
        h=hs[-1] if hs else None
        source_ok=h is not None and not (outage and outage[0]<=i/100<outage[1])
        records=[r for r in native if r['published']<=now]
        if source_ok and records and now<=records[-1]['expires']:
            action_ok+=1
        published=[r for r in frames if r[0]<=now]
        if source_ok and published:
            _,raw,out=published[-1]
            try:
                # Simulate a successful current health read. Transport latency
                # and production CPU contention are NOT included in this grid.
                validate(raw,dict(h,observed=now),now)
                info_ok+=1
            except ValueError:
                pass
    summarize=lambda xs:dict(count=len(xs),median_s=statistics.median(xs),max_s=max(xs)) if xs else None
    return dict(scenario=name,duration_s=duration,grid_s=.01,brti_age_at_source_event_s=delay,
                source_updates_s=1,native_cadence_s=5,information_poll_phase_delay_s=.25,quote_interruption_s=outage,
                information_available_samples=info_ok,action_available_samples=action_ok,samples=count,
                information_availability_pct=100*info_ok/count,
                authoritative_availability_pct=100*action_ok/count,
                improvement_percentage_points=100*(info_ok-action_ok)/count,
                additional_information_publications=len(frames)-len(native),
                native_decisions=len(native),information_publications=len(frames),
                inference_and_health=summarize(inference),native_export_capture=summarize(export_cost))


def main():
    initial=FrozenRuntime(completed());model=FairAssessment()
    result=dict(schema='BTC15_TWO_CLOCK_INFORMATION_MEASUREMENT_V1',
        scope='Synthetic January 2020 source/clock replay; real frozen model and measured local inference/export costs',
        excluded=['live network latency','production resource contention','browser/network delivery latency',
                  'predictive or trading performance','validation cohort'],
        authoritative_clock_changed=False,production_measured_improvement=None,
        scenarios=[run('representative_2_486s',initial,model),
                   run('quote_interruption_10_to_14s',initial,model,outage=(10,14)),
                   run('late_4_4s_source',initial,model,delay=4.4)])
    target=ROOT/'completion_audit/TWO_CLOCK_AVAILABILITY_20260925.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
