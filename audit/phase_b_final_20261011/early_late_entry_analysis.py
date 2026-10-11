"""Offline characterization only. No runtime hook, trading gate or price forecast."""
import json
from decimal import Decimal


def unknown_mean_threshold(target, count, average):
    """Raw-average break-even of the UNOBSERVED seconds (not just future seconds).

    Inputs must come from a causal same-contract snapshot. This arithmetic does
    not verify that provenance, model a future distribution, or apply official
    settlement rounding. It must never be used as a BUY/lock decision by itself.
    """
    if type(count) is not int or not 0 <= count < 60:
        raise ValueError('PARTIAL_COUNT_REQUIRED')
    t, a = Decimal(str(target)), Decimal(str(average))
    if not t.is_finite() or not a.is_finite() or t <= 0 or a <= 0:
        raise ValueError('FINITE_POSITIVE_VALUES_REQUIRED')
    return (Decimal(60)*t-Decimal(count)*a)/Decimal(60-count)


def characterize():
    from test_btc15_supported_early import value_frame, step
    from btc15_v2_product.directional import Directional
    observations=[]
    for side in ('UP', 'DOWN'):
        sign=1 if side=='UP' else -1
        for left in (899.,600.,300.,120.,60.,29.1,15.,5.,1.1):
            f=value_frame(ask=.05,p=.83,offset=900-left,side=side)
            n=max(0,min(59,int(60-left)))
            f['brti'].update(final60_count=n,final60_avg=f['target']-sign*20 if n else None,
                final60_side=('DOWN' if side=='UP' else 'UP') if n else None,final60_complete=False)
            engine=Directional();engine.restore({});record,_,view=step(engine,f)
            observations.append(dict(side=side,seconds_left=left,event=record.get('event'),
                observed_source_delay=view.get('origin',{}).get('qualification',{}).get('risk',{}).get('observed_source_delay'),
                known_count=n,known_average=f['brti']['final60_avg'],
                unknown_mean_raw_break_even=str(unknown_mean_threshold(f['target'],n,f['brti']['final60_avg'])) if n else None,
                latest_brti=f['brti']['value'],signal_only=view['signal_only'],orders=view['orders']))
    return dict(evidence_class='SYNTHETIC_CHARACTERIZATION_NOT_INCIDENT_REPLAY',
        production_change=False,proposed_gate_implemented=False,observations=observations,
        incident_nearby_log_arithmetic=[
            dict(at='2026-10-11T14:29:22Z',known_count=20,rounded_log_average='82991.01',
                 unknown_seconds=40,approx_raw_break_even=str(unknown_mean_threshold('83008.51',20,'82991.01'))),
            dict(at='2026-10-11T14:29:53Z',known_count=52,rounded_log_average='83002.06',
                 unknown_seconds=8,approx_raw_break_even=str(unknown_mean_threshold('83008.51',52,'83002.06')))],
        limitation='Log averages are rounded and not the issuance snapshot. Unknown seconds include delayed/missing past samples. No inferred fills, profits, exact incident feasibility or calibrated probability.')


if __name__=='__main__':
    print(json.dumps(characterize(),indent=2))
