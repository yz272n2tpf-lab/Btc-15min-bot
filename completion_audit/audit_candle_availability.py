"""Demonstrate historical candle availability mismatch without running the bot."""
import ast
import json
from pathlib import Path
import numpy as np
import pandas as pd

root=Path(__file__).resolve().parents[1]
tree=ast.parse((root/'bot_two_output_build_v4_13_profit_protection_shadow.py').read_text())
names={'_fair_price_at_or_before','_fair_build_snapshot'}
nodes=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in names]
assert len(nodes)==2
env=dict(pd=pd,np=np)
exec(compile(ast.Module(body=nodes,type_ignores=[]),'<pure existing feature functions>','exec'),env)
opened=pd.Timestamp('2026-09-23T12:30:00Z')
cut=opened+pd.Timedelta(minutes=5)
index=pd.date_range(opened-pd.Timedelta(minutes=5),cut,freq='min')
bars=pd.DataFrame(dict(Open=100.,High=101.,Low=99.,Close=100.,Volume=1.),index=index)
before=env['_fair_build_snapshot'](bars,opened,100.,_cut=cut)
# Bucket indexed12:35 describes trades through12:35:59. Its eventual close
# and high are not known at the12:35 decision cutoff.
mutated=bars.copy();mutated.loc[cut,['Close','High']]=[150.,151.]
after=env['_fair_build_snapshot'](mutated,opened,100.,_cut=cut)
changes={k:dict(before=before[k],after=after[k]) for k in before if before[k]!=after[k]}
result=dict(cutoff_utc=cut.isoformat(),mutated_bucket_start_utc=cut.isoformat(),
            bucket_complete_utc=(cut+pd.Timedelta(minutes=1)).isoformat(),
            existing_future_guard_raised=False,changed_features=changes,
            conclusion='Historical completed bucket values alter features at bucket start, before their availability.',
            source='https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles',
            production_changed=False,orders=False)
(root/'completion_audit/candle_availability_reproduction.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
