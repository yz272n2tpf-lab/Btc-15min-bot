"""Bounded stress measurements; synthetic only, never a live duration claim."""
from pathlib import Path
import json,resource,statistics,time,threading,tracemalloc
from .policy import config,proposed_policy
from .integration import Capture
from candidates.early_recording_20261012.archive import canonical

def percentile(values,p):
    return sorted(values)[min(len(values)-1,int(len(values)*p))] if values else None

def measure(path,rate,seconds,*,large_levels=0):
    cap=Capture(config(path,enabled=True,run_id='fixture-capacity'));o=cap.observer
    elapsed=[];count=0;accepted=0;start=time.perf_counter();wall_start=time.time();max_lag=0
    latency=[];processing=[];observe=cap.archive.observe
    def measured(kind,fields):
        begin=time.monotonic_ns()
        result=observe(kind,fields)
        if kind=='QUOTE_RECEIVE':
            processing.append((time.monotonic_ns()-begin)/1000)
            latency.append((time.monotonic_ns()-fields['monotonic_ns'])/1000)
        return result
    cap.archive.observe=measured
    initial=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    tracemalloc.start()
    # Mixed evidence role sizes (book + source + information), all required
    # raw observations submitted without queue.join pacing on the source path.
    while time.perf_counter()-start<seconds:
        deadline=start+count/rate
        now=time.perf_counter()
        if now<deadline:time.sleep(deadline-now)
        received=1000+count/rate
        event=dict(type='orderbook_delta',sid=7,seq=count+2,msg=dict(market_ticker='FIXTURE',market_id='fixture-id',
            side='yes',price_dollars='0.40',delta_fp='0.25',ts_ms=int(received*1000)))
        if large_levels:
            event=dict(type='orderbook_snapshot',sid=7,seq=count+1,msg=dict(market_ticker='FIXTURE',market_id='fixture-id',
                yes_dollars_fp=[[f'{(i+1)/(large_levels+2):.8f}','12345.125'] for i in range(large_levels)],
                no_dollars_fp=[['0.01','10']]))
        raw=canonical(event);t=time.perf_counter_ns()
        ok=o.quote_receive(raw,'FIXTURE','e',received+.01,time.monotonic_ns())
        ok=o.quote_accept(raw,'FIXTURE','e',received+.01,received+.02) and ok
        if count%max(1,int(rate))==0:
            o.source('BTC',100000+count,received,received+.01,'b')
            o.source('BRTI',100001+count,received,received+.01,'z')
            # Original raw information capture shape; exact input hash verified
            # mechanically, not model inference or fabricated market observation.
            cap.writer.submit_observation('INFORMATION_INPUT',raw=canonical(dict(anchor=dict(ticks=[],completed=[],decision=received),
                proof=dict(events=[]),cut=received)),published=False)
        elapsed.append((time.perf_counter_ns()-t)/1000);accepted+=int(ok);count+=1
        max_lag=max(max_lag,time.perf_counter()-deadline)
    produce=time.perf_counter()-start
    ok=cap.close(timeout=10);duration=time.perf_counter()-start
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    size=sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())
    result=dict(evidence='FIXTURE_ONLY',rate_target=rate,seconds_target=seconds,large_levels=large_levels,
        quote_messages_attempted=count,quote_pairs_accepted=accepted,produce_seconds=produce,total_seconds=duration,
        disk_bytes=size,bytes_per_second=size/produce,peak_python_bytes=peak,
        process_peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        prior_process_peak_RSS_KiB=initial,p50_admission_us=percentile(elapsed,.5),p99_admission_us=percentile(elapsed,.99),
        p99_receive_to_durable_us=percentile(latency,.99),p99_archive_processing_us=percentile(processing,.99),max_admission_us=max(elapsed),max_schedule_lag_ms=max_lag*1000,status=cap.status(),graceful=ok,
        complete_lossless=ok and not cap.status()['losses'] and not cap.status()['archive_failed'])
    return result

def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    results=[]
    # ~18 seconds total offered load. These are not measured current feed rates.
    for name,rate,seconds,levels in [('sustained',100,8,0),('high',700,6,0),('burst',3000,2,0),('large_valid',4,2,10000)]:
        results.append(dict(name=name,**measure(out/name,rate,seconds,large_levels=levels)))
        (out/(name+'.measurement.json')).write_bytes(canonical(results[-1]))
    # Lossy measured growth underestimates offered input. Scale by acceptance
    # only as a planning lower bound; qualification stays blocked if any drops.
    small=[r for r in results if not r['large_levels'] and r['complete_lossless']]
    per_message=max(r['disk_bytes']/r['quote_messages_attempted'] for r in small)
    offers=[per_message*r['rate_target'] if not r['large_levels'] else r['bytes_per_second'] for r in results]
    try:proposal=proposed_policy(max(offers))
    except ValueError as exc:proposal=dict(status='BLOCKED',reason=str(exc),required_per_archive_bytes=max(offers)*(86400+120+420)*1.5,allocation_performed=False)
    value=dict(results=results,proposed_local_policy=proposal,actual_live_rate_verified=False,
        full_duration_capacity='BLOCKED',reason='Accelerated fixture plus dependency/retrieval blockers; no live throughput/RSS qualification',
        costs_or_cloud_allocation_authorized=False,assumptions=dict(duration_seconds=86400,warmup_seconds=120,
        finalization_seconds=420,margin=1.5,archive_instances=2,spool_reclamation=False,
        missing_costs=['live CPU contention','actual information/proof rate','existing production volume usage']))
    (out/'CAPACITY_RESULTS.json').write_bytes(canonical(value));return value

if __name__=='__main__':
    import sys
    print(json.dumps(run(sys.argv[1]),sort_keys=True))
