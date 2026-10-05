"""Assembled dashboard fixtures come from the real frozen processors."""
import json
from pathlib import Path
from btc15_v2_product.journal import ProcessorEnvelope
from btc15_ladder_product_v1 import Directional
from btc15_scalp_journal_v1 import Scalp
from test_btc15_ladder_completion_v1 import frame,OPEN
from test_btc15_scalp_journal_v1 import state
from btc15_v2_product import REVISION

def build():
    main=ProcessorEnvelope(Directional(),'main');main.restore({})
    for i in range(2):
        f=frame(offset=300+i*5,sequence=i+1,p=.95 if i else .8)
        _,_,m=main.process((f,'test'+str(i)),f['captured_ts']+.01)
    scalp=ProcessorEnvelope(Scalp(),'v81');scalp.restore({})
    for i,(off,bid) in enumerate([(300,.34),(301,.34),(302,.72),(303,.70),(304,.68),(305,.68)]):
        f=state(OPEN+off,bid,i+1);_,_,s=scalp.process((f,'test'+str(i)),f['captured_ts']+.01)
    now=OPEN+305.02;m['served_ts']=s['served_ts']=now
    q=dict(schema='BTC15_EXECUTABLE_QUOTE_R1',revision=REVISION,authority='PRICE_PRESENTATION_ONLY',
        signal_only=True,orders=False,status='AVAILABLE',official_identity=m['official_identity'],epoch='q',market_id='m',
        sid=1,sequence=50,exchange_ts=now-.2,accepted_ts=now-.1,published_ts=now-.01,served_ts=now,
        expires_at=now+5.8,up_bid=.34,up_ask=.35,down_bid=.65,down_ask=.66)
    from test_btc15_read_only_revalidation import source,Evaluator
    from btc15_v2_product.revalidation import Revalidator,apply
    native=frame(offset=305,sequence=2,p=.95)
    checked=OPEN+311.02
    confirmation=Revalidator(Evaluator(.95),lambda:checked).step(m,source(native,checked))
    renewed=apply(m,confirmation,checked)
    assert renewed['status']!='UNAVAILABLE',renewed
    assert checked>renewed['presentation_revalidation']['native_expires_at']
    path=Path('qualification/v2_product_20261004/ui_fixture.json')
    path.write_text(json.dumps(dict(main=m,main_revalidated=renewed,scalp=s,quote=q,evidence_class='FIXTURE'),indent=2)+'\n')
    print(path)

if __name__=='__main__':build()
