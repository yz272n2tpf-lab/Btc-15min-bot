"""One bounded synthetic capture-to-reader-to-report and staging rehearsal."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import json,os,socket,subprocess,sys,threading,time
from unittest.mock import patch,Mock
from .policy import config
from .integration import Capture
from .evidence import index_run,file_sha,records_for,independent_history
from .report import generate
from .transfer import package,restore
from .staging import make_target,install,rollback,ROOT
from candidates.early_recording_20261012.archive import canonical,sha,reconstruct
from btc15_quote_proof_offpath_v1 import OffPathProofWriter
from btc15_brti_delivery_v1 import Delivery
from btc15_v2_product.bootstrap import PreparedProvider
import btc15_kalshi_quote_provenance_v1 as quotes

def fixture_provider(path,ticker,closed):
    p=PreparedProvider.__new__(PreparedProvider);p.lock=threading.Lock()
    p.ticker=ticker;p.close_ms=int(closed*1000);p.book=None;p.events=[];p.epoch=None
    def validate(proof,w):
        quotes.replay(proof,w.source_time,w.ticker,w.close_ms,w.consumed_ms);return w.identity
    p.proof_writer=OffPathProofWriter(path,validate,quotes.MAX_BYTES)
    return p

def source_fixture(clock):
    ns={'_brti_delivery':Delivery()}
    def read():
        t=clock[0];value=100000+t%900/10
        ns['_btc_spot_provenance']=dict(price=value,source_utc=datetime.fromtimestamp(t-.1,timezone.utc),
            observed_utc=datetime.fromtimestamp(t,timezone.utc))
        return value
    ns['get_btc_spot']=read;return ns

def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    c=config(out/'run',enabled=True);(out/'config.json').write_bytes(canonical(c))
    # No test can accidentally collect upstream data.
    with patch('socket.socket.connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch('socket.create_connection',side_effect=AssertionError('NETWORK_FORBIDDEN')):
        return _run(out,c)

def _run(out,c):
    from test_btc15_isolated_decision_v2 import OPEN,completed,fixture
    from completion_audit.isolated_decision_v2 import FrozenRuntime,stable
    from test_btc15_information_v1 import Rig
    from btc15_information_service_v1 import DurablePublisher
    from btc15_information_v1 import FairAssessment
    cap=Capture(c);clock=[OPEN+780.2];ns=source_fixture(clock);cap.bind_sources(ns)
    sends=[];calls=0;proof_outputs=[]
    for ticker,start,end,closed in [('FIXTURE-A',180,899,900),('FIXTURE-B',900,1321,1800)]:
        provider=fixture_provider(out/('proof-'+ticker),ticker,OPEN+closed);cap.bind_provider(provider)
        seq=[0]
        class WS:
            def send(self,raw):sends.append(raw)
            def recv(self,timeout=1):
                nonlocal calls
                offset=start+seq[0];calls+=1
                if offset>end:raise EOFError('fixture end, not live disconnect')
                clock[0]=OPEN+offset+.2
                ns['get_btc_spot']();ns['_brti_delivery'].accept(100001+offset/10,OPEN+offset,clock[0]-.01,'fixture-brti')
                seq[0]+=1
                if seq[0]==1:
                    event=dict(type='orderbook_snapshot',sid=7,seq=1,msg=dict(market_ticker=ticker,market_id=ticker+'-id',
                        yes_dollars_fp=[['0.40','1000.25']],no_dollars_fp=[['0.59','1000.50']]))
                else:event=dict(type='orderbook_delta',sid=7,seq=seq[0],msg=dict(market_ticker=ticker,market_id=ticker+'-id',
                    side='yes',price_dollars='0.40',delta_fp='0.25',ts_ms=int((OPEN+offset)*1000)))
                # Deterministic E2E functional pacing only. Unpaced/paced overhead
                # and losses are measured separately by capacity.py.
                if seq[0]%4==0:cap.writer.queue.join()
                return json.dumps(event,separators=(',',':'))
        with patch.object(quotes.time,'time',side_effect=lambda:clock[0]),patch.object(quotes.rollover_diag,'emit'):
            try:provider.session(WS(),ticker)
            except EOFError:pass
            result=provider.consume(ticker,'fixture-decision',provider.close_ms)
        provider.proof_writer.queue.join();provider.proof_writer.close()
        latest=out/('proof-'+ticker)/'latest.json'
        assert result is not None and latest.is_file(),'EXISTING_PROOF_CONSUMER_PRESERVED'
        proof_outputs.append(json.loads(latest.read_bytes()))
        cap.observer.clock=lambda:clock[0]
        cap.observer.http('/trade-api/v2/markets/'+ticker,canonical(dict(market=dict(ticker=ticker,event_ticker=ticker,
            open_time=OPEN+closed-900,close_time=OPEN+closed,floor_strike=100000,source='SYNTHETIC'))))
    # Actual information publisher seam; no refit, forecast evaluation or labels.
    rig=Rig(FrozenRuntime(completed()),offset=300)
    pub=DurablePublisher(FairAssessment(),journal_path=out/'information-frames',**cap.publisher_kwargs());cap.attach_publisher(pub)
    raw=rig.export.capture();assert pub.offer(raw,rig.export.health,lambda:rig.at)
    # Exact native loop parity through the staging capture binding on supplied
    # fixed fixtures. Source callbacks are changed; protected reducers are not.
    original=FrozenRuntime(completed());observed=FrozenRuntime(completed())
    # Separate session keeps the synthetic chronology of this mechanical parity
    # fixture distinct from the continuous rollover evidence above.
    paritycap=Capture(config(out/'parity',enabled=True,run_id='fixture-parity'))
    paritycap.bind_sources(observed.ns,tick=True)
    parity=[]
    for elapsed in (120,125,130,600,605,895,900,905):
        f=fixture(elapsed,ticker='KXBTC15M-19DEC311930-30') if elapsed>=900 else fixture(elapsed)
        expected=original.step(deepcopy(f));actual=observed.step(deepcopy(f))
        assert stable(expected)==stable(actual)
        assert stable(original.snapshot())==stable(observed.snapshot())
        parity.append(elapsed);paritycap.writer.queue.join()
    paritycap.close();cap.writer.queue.join();cap.close()
    index=index_run(out/'run',out/'finalized/index')
    quality=generate(out/'run',out/'finalized/index',out/'finalized/report',health=cap.status())
    transfer=package(out/'run',out/'finalized/index',out/'review-store',quota=512*1024**2,
        identity=json.loads((out/'run/identity.json').read_bytes()),report=out/'finalized/report/quality.json')
    cmd=[sys.executable,'-B','-m','ops.recording_workflow.operator','restore','--manifest',transfer['manifest'],
         '--sha256',transfer['sha256'],'--output',str(out/'clean-reader')]
    child=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (out/'CLEAN_READER.txt').write_text(child.stdout+child.stderr);assert child.returncode==0,child.stderr
    # Reader builds its own index and automatic report from restored original bytes.
    index_run(out/'clean-reader',out/'reader-index')
    reader_report=generate(out/'clean-reader',out/'reader-index',out/'reader-report')
    assert reader_report['counts']==quality['counts']
    assert reader_report['mechanics']==quality['mechanics'] or reader_report['mechanics']['original_input_hashes']==quality['mechanics']['original_input_hashes']
    restore(transfer['manifest'],out/'independent-restoration',expected_sha256=transfer['sha256'])
    target=make_target(out/'target');installed=install(out/'target')
    # Import installed integration without running any service or source.
    check=subprocess.run([sys.executable,'-B','-c','from ops.recording_workflow.integration import Capture; from ops.recording_workflow.policy import config; c=Capture(config("./never-created",enabled=False)); assert c.status()["status"]=="DISABLED"'],cwd=out/'target',capture_output=True,text=True)
    (out/'TARGET_IMPORT.txt').write_text(check.stdout+check.stderr);assert check.returncode==0,check.stderr
    reverted=rollback(out/'target')
    result=dict(status='VERIFIED_OFFLINE_WORKFLOW',fixture_only=True,network_calls=0,
        span_seconds=1142,predecision_seconds=120,postdecision_seconds=421,
        source_coverage=index['coverage'],fixed_input_parity_offsets=parity,
        existing_proof_consumer_hashes=[x['sha256'] for x in proof_outputs],
        subscription_commands=len(sends),recv_calls=calls,package=transfer,
        clean_reader='VERIFIED_SEPARATE_PROCESS',automatic_report='VERIFIED',
        target=target,installation=installed,rollback=reverted,
        live_export='BLOCKED',live_24h='NOT_RUN',predictive_evaluation=False)
    (out/'REHEARSAL_RESULTS.json').write_bytes(canonical(result));return result
