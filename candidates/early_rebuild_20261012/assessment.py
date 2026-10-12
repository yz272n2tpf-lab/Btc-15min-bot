"""Two-sided causal recognition, execution checks and unestimated resale quality."""
from dataclasses import dataclass
import math
from candidates.early_value_20261011.engine import Rules as BaselineRules
from candidates.early_value_20261011.qualification import features as baseline_features

SAFETY = dict(signal_only=True, orders=False, production_enabled=False, actionable=False)
TARGET = 'EXPECTED_NET_CENTS_AFTER_DELAYED_ENTRY_AND_BASELINE_CONDITION_EXIT'

@dataclass(frozen=True)
class Rules(BaselineRules):
    # Retained provisional mechanics, not estimated optimal strategy settings.
    min_left: float = 180
    exit_execution_seconds: float = 10
    refresh_seconds: float = 10


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def validate_row(r):
    required = ('time','received','left','target','btc','brti','p',
                'up_bid','up_ask','down_bid','down_ask')
    if any(not finite(r.get(k)) for k in required): return ['INVALID_NUMERIC']
    if not r.get('contract') or not r.get('publication_id') or not r.get('source_epoch'):
        return ['IDENTITY_REQUIRED']
    if r.get('side') not in ('UP','DOWN') or not .5 <= r['p'] <= 1:
        return ['INVALID_SETTLEMENT_PROBABILITY']
    if not r.get('healthy') or r['target'] <= 0 or min(r['btc'],r['brti']) <= 0:
        return ['UNHEALTHY_SOURCE']
    if not 0 <= r['received']-r['time'] <= 10 or r['left'] <= 0:
        return ['STALE_OR_EXPIRED_OBSERVATION']
    if (not 0 <= r['up_bid'] <= r['up_ask'] <= 1 or
        not 0 <= r['down_bid'] <= r['down_ask'] <= 1 or
        abs(r['up_bid']+r['down_ask']-1)>1e-7 or
        abs(r['down_bid']+r['up_ask']-1)>1e-7):
        return ['INVALID_SAME_SIDE_BOOK']
    return []


def features(history, r, side, rules):
    x = baseline_features(history, r, side, rules)
    if x is None: return None
    sign = 1 if side=='UP' else -1
    cutoff = r['time']-rules.short
    old = next(z for z in reversed(history) if z['time']<=cutoff)
    seq = [z for z in history if old['time']<=z['time']<=r['time']]
    increments = {k:[sign*(b[k]-a[k]) for a,b in zip(seq,seq[1:])]
                  for k in ('btc','brti')}
    x['brti_efficiency'] = x['brti_short']/max(sum(abs(v) for v in increments['brti']),1e-6)
    x['movement_persistence'] = {k:sum(v>0 for v in vv)/max(len(vv),1)
                                 for k,vv in increments.items()}
    # Diagnostic acceleration over two observed half-windows, no interpolation.
    mid = next((z for z in reversed(seq) if z['time']<=r['time']-rules.short/2),None)
    x['acceleration'] = {k:sign*((r[k]-mid[k])/(r['time']-mid['time'])-
                              (mid[k]-old[k])/(mid['time']-old['time']))
                         for k in ('btc','brti')} if mid and mid['time']>old['time'] else None
    x['target_location'] = ('ALIGNED' if min(x['gap'],x['brti_gap'])>0 else
                            'OPPOSITE' if max(x['gap'],x['brti_gap'])<0 else 'MIXED_OR_AT_TARGET')
    x['context'] = 'CONTINUATION' if x['target_location']=='ALIGNED' else 'PRE_CROSSING'
    x['strong_sub25'] = bool(x['context120_available'] and min(x['move_long'],x['brti_long'])>0
                            and all(v>=0 for vv in increments.values() for v in vv)
                            and min(x['move_short'],x['brti_short'])>0)
    return x


def recognition_reasons(x, rules):
    if x is None: return ['CAUSAL_30S_HISTORY_UNAVAILABLE']
    checks = dict(FRESH_BTC_BRTI_IMPULSE=min(x['move_short'],x['brti_short'])>=rules.impulse_range*x['short_range'],
                  BTC_PATH_EFFICIENCY=x['short_efficiency']>=rules.efficiency,
                  BRTI_PATH_EFFICIENCY=x['brti_efficiency']>=rules.efficiency,
                  NO_MATERIAL_QUOTE_REVERSAL=x['quote_short']>=-max(x['spread'],.01)-1e-9)
    return [k for k,v in checks.items() if not v]


def price_group(ask):
    return 'SUB25' if ask<.25 else 'PRIMARY' if ask<=.55 else 'EXCEPTION56_58' if ask<=.58 else 'ABOVE58'


def execution_reasons(r, side, x, rules):
    ask,bid = r[side.lower()+'_ask'], r[side.lower()+'_bid']
    reasons=[]
    if not 0<bid<=ask<=.58: reasons.append('PRICE_ABOVE58_OR_NO_POSITIVE_BID')
    if ask-bid>rules.max_spread+1e-9: reasons.append('SPREAD_TOO_WIDE')
    # All times are separate budgets. 180s is provisional development room, NOT a sell timer.
    if r['time']+r['left']-r['received'] <= rules.min_left+rules.manual_seconds+rules.exit_execution_seconds:
        reasons.append('INSUFFICIENT_MANUAL_AND_MANAGEMENT_RUNWAY')
    if ask<.25 and not (x and x['strong_sub25']): reasons.append('SUB25_STRONGER_DIRECTIONAL_EVIDENCE_MISSING')
    return reasons


def source_reasons(r, now, *, fixture_mode=False, registry=None, side=None, quantity=None):
    """Retained rows require actual bound inputs; no healthy flag or fixture promotion."""
    if fixture_mode and r.get('evidence_class')=='SYNTHETIC_FIXTURE':
        return [] if r['time']<=now<r['time']+10 else ['SOURCE_EXPIRED']
    if not isinstance(r.get('native_frame'),dict):
        return ['NATIVE_QUOTE_BRTI_RECEIPTS_MISSING','AUTHORITATIVE_CLOSE_BINDING_MISSING',
                'CAUSAL_FEATURE_BINDING_NOT_COMPLETE','DEPTH_AND_FEE_APPLICABILITY_UNVERIFIED']
    from .execution import execution_assessment
    return execution_assessment(r,side or r['side'],now,registry,quantity)['blockers']


def economic_assessment(r, side, x):
    group=price_group(r[side.lower()+'_ask'])
    return dict(target=TARGET, side=side,context=x['context'] if x else None,price_group=group,
                status='UNESTIMATED',ready=False,expected_net_cents=None,lower95_net_cents=None,
                downside_tail_cents=None,independent_complete_contracts=0,
                reasons=['NO_SUPPORTED_CONDITIONAL_RESALE_ESTIMATE','NO_UNTOUCHED_ECONOMIC_EVALUATION',
                         'DOWNSIDE_AND_PRICE_RUNWAY_SUPPORT_UNESTIMATED']+
                        (['SEPARATE_'+group+'_ECONOMIC_SUPPORT_MISSING'] if group!='PRIMARY' else []),
                uncertainty='Not estimable; observations are dependent and execution paths unverified',
                basis='First admissible observed BID after baseline condition EXIT and exit delay, minus refreshed ASK, both fees and reserve',
                settlement_probability_is_not_resale_probability=True)


def assess(history,r,side,rules,fixture_mode=False,*,registry=None,quantity=None):
    x=features(history,r,side,rules)
    return dict(side=side,features=x,recognized=not recognition_reasons(x,rules),
                recognition_blockers=recognition_reasons(x,rules),
                execution_blockers=execution_reasons(r,side,x,rules),
                source_blockers=source_reasons(r,r['received'],fixture_mode=fixture_mode,registry=registry,side=side,quantity=quantity),
                economics=economic_assessment(r,side,x),
                settlement_probability=r['p'] if r['side']==side else 1-r['p'],
                ask=r[side.lower()+'_ask'],bid=r[side.lower()+'_bid'])
