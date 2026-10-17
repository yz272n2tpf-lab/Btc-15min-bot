"""Conditional 10/12-hour arithmetic, never a capture launcher or validator.

Short incomplete bursts and synthetic SQL ratios are explicitly NOT sustained
native measurements. Startup sample is added once, then a 50% margin applied.
"""
import argparse
import json
import math
from pathlib import Path

GiB=1024**3
MARGIN=1.5
TAIL=540  # existing 120-second preparation + 420-second settlement allowance


def scenarios(baseline):
    rows=[]
    for hours in (10,12):
        horizon=hours*3600+TAIL;roles={};db=0
        for role,m in baseline['roles'].items():
            n=m['burst_envelopes_per_second']*horizon
            base=dict(records=n+m['records'],compressed=n*m['compressed']/m['records']+m['compressed'],
                      decoded=n*m['decoded']/m['records']+m['decoded'])
            guarded={k:math.ceil(v*MARGIN) for k,v in base.items()}
            mix=baseline['reader_stress']['source' if role=='main' else 'quote']
            sql_bytes=base['records']*mix['db_bytes']/mix['envelopes'];db+=sql_bytes
            roles[role]=dict(conditional_base={k:math.ceil(v) for k,v in base.items()},
                with_margin=guarded,synthetic_sql_mix=sql_bytes,
                same_volume_free_required_excluding_information=guarded['compressed']+2*GiB)
        compressed=sum(v['conditional_base']['compressed'] for v in roles.values())
        guarded_compressed=sum(v['with_margin']['compressed'] for v in roles.values())
        guarded_db=math.ceil(db*MARGIN)
        rows.append(dict(hours=hours,evaluation_seconds=hours*3600,horizon_seconds=horizon,
            full_contracts_if_boundary_aligned=hours*4,roles=roles,
            reader=dict(synthetic_sql_bytes=math.ceil(db),with_margin_bytes=guarded_db,
                current_ceiling_bytes=48*GiB,
                within_current_ceiling=guarded_db<=48*GiB,
                conservative_workspace_bytes=2*guarded_db+guarded_compressed+10*GiB,
                workspace_basis='DB + full DB rollback contingency + one source copy + 8 GiB ledger/export allowance + 2 GiB operating reserve; information role and existing usage excluded'),
            monthly_storage_usd_if_actual_retained=dict(producer_base=compressed/1e9*.15,
                producer_margin_as_data=guarded_compressed/1e9*.15,
                sql_margin_as_data=guarded_db/1e9*.15),
            costs_exclude=['information','historical usage','native journals','extra source copies',
                           'CPU','RAM','egress','subscription/credits'],
            healthy_native_measurements_required=True,approved=False))
    return dict(schema='BTC15_EARLY_10_12H_CONDITIONAL_PLAN_V1',margin=MARGIN,
        basis='INCOMPLETE_SHORT_BURST_RATE_PLUS_ONE_STARTUP_SAMPLE; NOT_FORECAST',
        pricing_source='https://docs.railway.com/pricing/plans',
        queue=dict(current_bytes=32*1024**2,current_items=16384,
           maximum_measured_deficit_for_1_5x_margin_bytes=math.floor(32*1024**2/MARGIN),
           maximum_measured_item_deficit_for_1_5x_margin=math.floor(16384/MARGIN),
           formula='1.5 * max_t(cumulative admitted charge - durably completed charge); sustained drain must exceed arrivals',
           deficit_measured=False,unchanged_between_10_and_12_hours=True),scenarios=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,default=Path(__file__).with_name('baseline_metrics.json'))
    a=p.parse_args();print(json.dumps(scenarios(json.loads(a.baseline.read_text())),indent=2))
