"""Bounded synthetic product tape, not market/scoring evidence."""
import json
from pathlib import Path
import sys
from test_btc15_integrated_finish import directional,step,scalp_frame,OPEN
from test_btc15_ladder_completion_v1 import frame
from btc15_v2_product.journal import ProcessorEnvelope
from btc15_v2_product.scalp import Scalp
from btc15_v2_product import REVISION
from btc15_v2_product.installer import assemble

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
e=directional();s=ProcessorEnvelope(Scalp(),'v81');s.restore({});rows=[]
for n,(offset,p,ask,side,bid,scalp_side) in enumerate([
 (425,.6,.6,'UP',.59,'UP'),(426,.6,.6,'DOWN',.65,'UP'),
 (427,.6,.6,'UP',.61,'UP'),(430,.80,.35,'UP',.59,'DOWN'),
 (431,.85,.70,'UP',.59,'DOWN'),(432,.80,.70,'UP',.59,'DOWN'),
 (433,.95,.70,'UP',.59,'DOWN'),(434,.85,.70,'UP',.59,'DOWN'),
 (435,.95,.70,'UP',.59,'DOWN'),(612,.95,.70,'UP',.59,'DOWN')]):
 f=frame(offset=offset,sequence=n+1,p=p,ask=ask,side=side);r,_,main=step(e,f)
 sf=scalp_frame(OPEN+offset,bid,n+1,scalp_side);_,_,scalp=s.process((sf,'fixture'),sf['captured_ts']+.001)
 at=f['captured_ts']+.001
 for v in (main,scalp):v['served_ts']=at
 q=f['quote'];ident={k:f[k] for k in ('contract','target','official_open','official_close')}
 quote=dict(schema='BTC15_EXECUTABLE_QUOTE_R1',revision=REVISION,authority='PRICE_PRESENTATION_ONLY',
  signal_only=True,orders=False,status='AVAILABLE',official_identity=ident,published_ts=at,served_ts=at,
  exchange_ts=q['exchange_ts_ms']/1000,accepted_ts=q['consumed_ms']/1000,epoch=q['epoch'],sid=q['sid'],sequence=q['seq'],
  expires_at=min(f['official_close'],q['exchange_ts_ms']/1000+6),**{k:f[k] for k in ('up_bid','up_ask','down_bid','down_ask')})
 main['presentation_information']=dict(status='CHANGED',authority='INFORMATION_ONLY',signal_only=True,orders=False)
 rows.append(dict(at=at,main=main,scalp=scalp,quote=quote))
(out/'tape.json').write_text(json.dumps(rows))
assemble(out/'dashboard')
