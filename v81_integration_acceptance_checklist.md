# V8.1 Scalp Integration Acceptance Checklist

All items must pass before calling the scalp ladder integrated.

## Runtime/data
- [ ] Correct V8.1 scorer output attached to the decision.
- [ ] Runtime integrity PASS.
- [ ] BRTI freshness healthy and no material transport errors.
- [ ] Minimum sample requirement met for any graduated lane.

## Strategy behavior
- [ ] 30-45c protected behavior unchanged unless explicitly rejected by evidence.
- [ ] 15-30c uses only the evidence-approved route.
- [ ] 7-15c remains disabled.
- [ ] 3-7c remains disabled unless it explicitly graduates.
- [ ] No late sub-30 entries past the time guard.
- [ ] Confirmation count/window matches tested V8.1 behavior.

## App contract
- [ ] Shows UP/DOWN, not short terminology.
- [ ] Shows entry price and lane.
- [ ] Shows scalp opportunity separately from Final Outcome.
- [ ] Shows exit/profit guidance without automatic execution.
- [ ] Shows time left and flip/reversal risk context where available.

## Non-regression
- [ ] Final Outcome unchanged.
- [ ] Early Opportunity unchanged.
- [ ] Kalshi 15-minute clock/alignment unchanged.
- [ ] Kalshi pricing feed unchanged.
- [ ] BRTI transport unchanged.
- [ ] Logging/scoring still complete.
- [ ] Signal-only / manual trading only.

## Deployment
- [ ] Integration tested on isolated branch/service first.
- [ ] No production deploy until all checks above pass.
