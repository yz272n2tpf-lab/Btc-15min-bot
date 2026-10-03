"""Causal warning context, without new exit or probability thresholds."""


def context(side, seconds_left, *, btc, brti, target, weakening=False, giveback=False):
    sign = 1 if side == 'UP' else -1
    reasons = []
    if sign * (btc-target) <= 0:
        reasons.append('BTC_NOT_ON_HELD_SIDE_OF_TARGET')
    if sign * (brti-target) <= 0:
        reasons.append('BRTI_NOT_ON_HELD_SIDE_OF_TARGET')
    if weakening:
        reasons.append('DIRECTIONAL_SUPPORT_WEAKENING')
    if giveback:
        reasons.append('EXECUTABLE_PRICE_PULLBACK')
    phase = '3M_GUARD' if seconds_left <= 180 else '5M_CAUTION' if seconds_left <= 300 else 'NORMAL'
    # Time alone is context, never predictive EXIT authority. Three-minute
    # caution also applies to a strong position because executable runway ends.
    severity = 'CAUTION' if phase == '3M_GUARD' or (phase == '5M_CAUTION' and reasons) else 'WATCH' if reasons else 'HOLD'
    messages = list(reasons)
    if phase == '3M_GUARD':
        messages.append('FINAL_THREE_MINUTES_LIMITED_EXIT_RUNWAY')
    elif phase == '5M_CAUTION':
        messages.append('FINAL_FIVE_MINUTES_MONITOR_SUPPORT_AND_EXECUTABLE_BID')
    return dict(phase=phase, state=severity, reasons=messages, exit_authority=False)
