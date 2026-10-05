"""Small offline fault tape; identical native observations on baseline/candidate."""
from copy import deepcopy
import json,sys
from pathlib import Path
from btc15_ladder_product_v1 import Directional
from btc15_scalp_journal_v1 import Scalp
from btc15_v2_product.journal import ProcessorEnvelope,unavailable
from btc15_v2_product.revalidation import Revalidator,apply
from test_btc15_ladder_completion_v1 import frame,OPEN
from test_btc15_read_only_revalidation import source,Evaluator
from test_btc15_durable_handoff import frame as scalp_frame
from test_btc15_display_indicators import candles
from btc15_v2_product.indicators import calculate
from ops.btc15_v2_scoring.bridge import ticker
from btc15_v2_product import REVISION

def run():
    engines=[ProcessorEnvelope(Directional(),'main'),ProcessorEnvelope(Scalp(),'v81')]
    for e in engines:e.restore({})
    records=[];rows=[];now=[OPEN+425.01];evaluator=Evaluator();r=Revalidator(evaluator,lambda:now[0])
    for n,(offset,p,ask,side) in enumerate([(425,.6,.6,'UP'),(430,.8,.35,'UP'),(435,.95,.7,'UP'),(440,.6,.7,'DOWN'),(445,.95,.7,'UP'),(899,.6,.6,'UP'),(901,.6,.6,'UP')]):
        at=OPEN+offset;now[0]=at+.01;opened=int(at//900)*900
        f=frame(offset=offset,sequence=n+1,p=p,ask=ask,side=side)
        f.update(contract=ticker(opened),official_open=opened,official_close=opened+900)
        f['quote'].update(ticker=f['contract'],close_ms=int((opened+900)*1000))
        sf=scalp_frame(at,n*100+101,eligible=n in (1,2,3,4),bid=.34 if n<3 else .41 if n==3 else .36)
        sf['row']['target']=f['target'];sf['row']['input_provenance']['target']=f['target']
        for proposal in sf['proposals'].values():
            for h in proposal['history'].values():h['input_provenance']['target']=f['target']
        sf['diagnostics']=[dict(side='UP',reason=['PRICE_OUTSIDE_30_45C','BASE_NOT_READY','EVIDENCE_BELOW_CORE_SURGE'][n%3])]
        if n==2:
            prime=deepcopy(sf);prime=scalp_frame(at-1,n*100+100,eligible=True);records.append(['scalp_prime',engines[1].process((prime,'native'),at-.99)])
        a=engines[0].process((deepcopy(f),'native'),now[0]);b=engines[1].process((deepcopy(sf),'native'),now[0]);records.append([a,b])
        m=deepcopy(a[2]);s=deepcopy(b[2]);m['served_ts']=s['served_ts']=now[0]
        fresh=source(f,now[0],age=.1,sequence=n+1)
        q=dict(fresh['quote'],schema='BTC15_EXECUTABLE_QUOTE_R1',revision=REVISION,authority='PRICE_PRESENTATION_ONLY',signal_only=True,orders=False)
        end=int(at//60)*60;iv=calculate(candles(end),end,now[0]);iv['served_ts']=now[0]
        checkpoint=engines[0].processor.checkpoint();evaluator.p=1-f['fair']['up_fair']
        disagree=r.step(m,fresh);denied=apply(m,disagree,now[0]);assert denied['status']=='UNAVAILABLE',denied
        old=deepcopy(fresh);old['brti']['cf_ts']=now[0]-5.1
        expiry=Revalidator(Evaluator(f['fair']['up_fair']),lambda:now[0]).step(m,old)
        expired=apply(m,expiry,now[0]);assert expired['status']=='UNAVAILABLE'
        assert checkpoint==engines[0].processor.checkpoint()
        rows.append(dict(at=now[0],main=m,scalp=s,quote=q,indicators=iv,disagreement=denied,expired=expired))
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
    (out/'native.json').write_text(json.dumps(records,sort_keys=True,separators=(',',':')))
    (out/'tape.json').write_text(json.dumps(rows,separators=(',',':')))
    print(json.dumps({'main_events':[a[0].get('event') for a,b in records if a!='scalp_prime'],'scalp_events':[b[0].get('event') for a,b in records],'native_observations':sum(1 if a=='scalp_prime' else 2 for a,b in records)}))
if __name__=='__main__':run()
