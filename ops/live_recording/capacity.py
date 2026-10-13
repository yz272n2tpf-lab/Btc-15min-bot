"""Explicit 24-hour arithmetic; measurements never authorize a campaign."""
import math
from .policy import PROFILES,MiB,GiB
HORIZON=86400+120+420
MARGIN=1.5
def project(measurements):
 p=PROFILES['day'];out={};passed=True
 for role in ('main','v81','information'):
  m=measurements[role];peak=m['peak_rates'].get('steady',{});sample=m['elapsed']-120
  good=sample>=900 and all(peak.get(x,0)>0 for x in ('compressed','decoded','envelopes'))
  # Account for the actual warmup once, then worst measured steady interval
  # across every second of the entire horizon, plus 50% uncertainty margin.
  z={x:math.ceil((m[y]+peak.get(x,0)*HORIZON)*MARGIN) for x,y in [('compressed','compressed_bytes'),('decoded','raw_bytes'),('envelopes','records')]}
  share=2 if role=='main' else 4
  good=good and z['compressed']<p['compressed'][role]-6*MiB and z['decoded']<p['decoded']//share-5*MiB and z['envelopes']<p['records']//share-4
  out[role]=dict(projected=z,within_profile=good,measured_steady_seconds=sample,compressed_cap=p['compressed'][role],decoded_cap=p['decoded']//share,record_cap=p['records']//share)
  passed=passed and good
 return dict(schema='BTC15_24H_PROJECTION_V1',roles=out,within_profile=passed,qualified_24h=False,basis='MEASURED_PEAK_PROJECTION_PLUS_RUNTIME_FAILURE_STOP; NOT_A_FUTURE_RATE_GUARANTEE',horizon=HORIZON,margin=MARGIN,main_min_free_bytes=sum(p['compressed'][r] for r in ('main','information'))+GiB,v81_min_free_bytes=p['compressed']['v81']+GiB,codespace_min_free_bytes=p['db']+p['index']+3*sum(p['compressed'].values())+2*GiB,required_extra_gates=['real native timing comparison','private transfer throughput','reader disk/CPU/RSS/time','no original safety/proof drops','source completeness and rollover','exact installed dependencies','separate campaign authorization'])
