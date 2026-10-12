"""Deterministic protected FINAL/SCALP output fingerprint. Does not run live components."""
import hashlib,itertools,json
from btc15_v2_product.directional import protected_frame
from btc15_v2_product.scalp import Scalp
from test_btc15_ladder_completion_v1 import frame
from test_btc15_integrated_finish import scalp_frame
from test_btc15_scalp_journal_v1 import ENTRY

def result():
    finals=[]
    for side,p,left,gap in itertools.product(('UP','DOWN'),(.899999,.9,.95),(360,361,480,481),(49.999,50,74.999,75,80)):
        f=frame(offset=900-left,p=p,side=side);sign=1 if side=='UP' else -1
        f['btc_price']=f['target']+sign*gap;f['brti']['value']=f['btc_price']
        finals.append(protected_frame(f,f['captured_ts'])[0]['final'])
    scalps=[]
    for side in ('UP','DOWN'):
        engine=Scalp();engine.restore({})
        for i,(delta,bid) in enumerate(((0,.34),(1,.34),(2,.43),(3,.42),(4,.36),(30,.50)),1):
            f=scalp_frame(ENTRY+delta,bid,i,side)
            scalps.append(engine.process(f,f['captured_ts']+.001))
    packed=json.dumps(dict(final=finals,scalp=scalps),sort_keys=True,separators=(',',':'),default=str)
    return dict(final_cases=len(finals),scalp_cases=len(scalps),sha256=hashlib.sha256(packed.encode()).hexdigest())

if __name__=='__main__':print(json.dumps(result(),sort_keys=True))
