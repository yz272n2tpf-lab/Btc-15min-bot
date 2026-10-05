"""Accelerated 1-second product tape; native MAIN 5s, SCALP 1s, candles 60s.

Synthetic evidence, real frozen processors and repaired durable publication.
Actual-model/startup equivalence is independently covered by its native test.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from btc15_ladder_product_v1 import Directional,iso
from btc15_scalp_journal_v1 import Scalp
from btc15_v2_product import REVISION
from btc15_v2_product.journal import ProcessorEnvelope,public_view
from btc15_v2_product.durable_handoff import DurableWorker
from btc15_v2_product.revalidation import Revalidator,apply
from btc15_v2_product.indicators import calculate
from test_btc15_ladder_completion_v1 import frame,OPEN
from test_btc15_read_only_revalidation import source,Evaluator
from test_btc15_durable_handoff import frame as scalp_frame
from test_btc15_display_indicators import candles
from ops.btc15_v2_scoring.bridge import ticker


def main():
    main=ProcessorEnvelope(Directional(),'main');main.restore({})
    now=[OPEN+.51];revalidator=Revalidator(Evaluator(.6),lambda:now[0])
    rows=[];native_count=0
    with tempfile.TemporaryDirectory() as td:
        worker=DurableWorker(td,'v81',Scalp(),lambda:now[0])
        try:
            for second in range(960):
                at=OPEN+.5+second;now[0]=at+.01;opened=int(at//900)*900
                if second%5==0:
                    native_count+=1;f=frame(at-OPEN,native_count,p=.6,ask=.6)
                    f.update(contract=ticker(opened),official_open=opened,official_close=opened+900)
                    f['quote'].update(ticker=f['contract'],close_ms=int((opened+900)*1000))
                    _,_,v=main.process((f,'native'),now[0])
                    assert v['status']=='PASS',v
                fresh=source(f,now[0],age=.1,sequence=second+1)
                confirmed=revalidator.step(v,fresh);visible=apply(v,confirmed,now[0])
                assert visible['status']=='PASS',(second,visible)
                visible['served_ts']=now[0]
                q=dict(fresh['quote'],schema='BTC15_EXECUTABLE_QUOTE_R1',revision=REVISION,
                    authority='PRICE_PRESENTATION_ONLY',signal_only=True,orders=False)
                sf=scalp_frame(at,second+1,eligible=False)
                sf['row']['target']=80000.;sf['row']['input_provenance']['target']=80000.
                assert worker.offer(sf) and worker.wait_idle(5)
                scalp=public_view(td,'v81',now[0]);assert scalp['status']=='PASS',scalp
                end=int(at//60)*60
                indicators=calculate(candles(end),end,now[0]);indicators['served_ts']=now[0]
                identity=visible['official_identity'];close=identity['official_close']
                legacy=dict(contract=identity['contract'],generated_utc=iso(now[0]),source_timestamp_utc=iso(at-.1),
                    timer=dict(close_utc=iso(close)),safety=dict(read_only=True,orders_enabled=False),health=dict(paired_quotes=True),
                    parity=dict(contract=identity['contract'],api_contract=identity['contract'],status='PASS',timestamp_utc=iso(at)),
                    market=dict(target=80000.,btc_price=80080.,brti_value=80080.,brti_age_seconds=.1,brti_ready=True,brti_side='UP',up_ask=.6,down_ask=.4,preferred_side='UP'),
                    final=dict(side='UP',confidence=.6,ready=False,conditions={}),early=dict(ready=False,side='UP',ask=.6),scalp=dict(ready=False),
                    chart=dict(points=[dict(t=iso(at-60+n),brti=80010+n+(second%30)*.2,brti_age_sec=.1) for n in range(61)]))
                rows.append(dict(at=now[0],main=visible,scalp=scalp,quote=q,indicators=indicators,legacy=legacy))
            assert worker.accepted==worker.written==960 and worker.dropped==0
        finally:worker.close()
    out=Path('qualification/final_completion_20261005');out.mkdir(parents=True,exist_ok=True)
    (out/'product-tape.json').write_text(json.dumps(rows,separators=(',',':')))
    (out/'product-contract-backend.json').write_text(json.dumps(dict(status='PASS',seconds=960,
        main_native_decisions=native_count,scalp_native_decisions=960,source_expired_holes=0,
        decision_input_holes=0,scope='Synthetic qualified sources, actual frozen processors, accelerated clock'),indent=2)+'\n')
    print('PRODUCT TAPE PASS: 192 MAIN decisions / 960 durable SCALP publications / 960 complete product samples')


if __name__=='__main__':main()
