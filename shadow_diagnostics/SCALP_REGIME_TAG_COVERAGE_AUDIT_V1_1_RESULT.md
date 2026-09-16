# BTC15 Regime Tag Coverage Audit V1.1 — Corrected Result Freeze

**Mode:** CAUSAL FEATURE AUDIT / DESCRIPTIVE ONLY / NO OUTCOME SELECTION / NO THRESHOLD SELECTION / NO ORDERS  
**Source SHA-256:** `cfa8a54ce6cb47e6c9cee577ece3b52d356e383280a5fb42c5d77502c8e63aea`  
**Source rows:** `311408`  
**Source bytes:** `197816294`

V1.1 repairs only numeric `1.0/0.0` boolean interpretation. The causal audit allow-list, thresholds, chronological split, tag priority and serial lifecycle are unchanged. Future/path/outcome/economics fields are physically excluded from the audit records.

## Full serial-opportunity universe

- Serial opportunities audited: **457**
- All audited numeric and boolean features: **100% populated**
- `structure_ok`: 457/457 true
- BTC/BRTI agree5: 457/457 true
- BTC/BRTI agree15: 457/457 true
- BRTI primary health: 457/457 true
- BTC against-side: 0/457
- BRTI against-side: 0/457
- dual reversal evidence: 0/457
- observed reversal evidence: 0/457

These boolean fields therefore have no discriminatory variation inside the current serial candidate tape. This does **not** mean the entire BTC market is always aligned; it means candidates that reached this tape are uniform on these fields.

The research `baseline_qualified()` function itself requires only a valid side, >=120 seconds left and BTC30 >=15. The uniform structure/agreement flags arise in the candidate data available to the serial scorer, not from those three baseline-qualification checks alone.

## Trend funnel — fixed V1 thresholds

Existing descriptive Trend definition remains:
- structure true
- agree5 true
- agree15 true
- no reversal evidence
- BTC5 normalized momentum >=0.60
- BTC15 normalized momentum >=0.50

### All 457 opportunities
- BTC5 >=0.60: **215 / 457 = 47.05%**
- After BTC15 >=0.50: **210 / 457 = 45.95%**
- Final Trend-qualified: **210 / 457 = 45.95%**

Blockers:
- BTC5 norm <0.60: **242 / 457 = 52.95%**
- BTC15 norm <0.50: **110 / 457 = 24.07%**
- 105 opportunities had multiple momentum blockers.

BTC5 normalized momentum is the dominant Trend discriminator in this candidate universe.

### Validation
- 39 / 93 = **41.94%** Trend-qualified
- BTC5 <0.60 blocker: 54 / 93 = **58.06%**
- BTC15 <0.50 blocker: 22 / 93 = **23.66%**

### Holdout
- 42 / 96 = **43.75%** Trend-qualified
- BTC5 <0.60 blocker: 54 / 96 = **56.25%**
- BTC15 <0.50 blocker: 26 / 96 = **27.08%**

Holdout is descriptive only and cannot select a threshold.

## Kalshi-Lag funnel — fixed V1 threshold

Existing descriptive Lag add-on remains `abs(ask_move15) <= 0.02` after Trend qualification.

### All 457
- Trend-qualified before Kalshi response: 210
- Final Kalshi-Lag: **178 / 457 = 38.95%**
- `abs(ask15) > 0.02` blocker: **55 / 457 = 12.04%** overall

### Validation
- Trend: 39
- Kalshi-Lag: **35 / 93 = 37.63%**
- Ask-response blocker: 10 / 93 = 10.75% overall

### Holdout
- Trend: 42
- Kalshi-Lag: **38 / 96 = 39.58%**
- Ask-response blocker: 8 / 96 = 8.33% overall

The 2c repricing condition removes only a small subset after Trend already qualifies. Most tag scarcity comes from normalized BTC momentum, not missing Kalshi response telemetry.

## Acceleration funnel — fixed V1 threshold

Existing descriptive Acceleration definition keeps BTC5 normalized momentum >=0.75 and acceleration >0 after structure/agreement/no-reversal conditions.

- Acceleration is present and >0 for **457 / 457** opportunities.
- BTC5 norm >=0.75 is therefore the only observed blocker in this serial candidate universe.

All opportunities:
- **121 / 457 = 26.48%** Acceleration-qualified

Validation:
- **27 / 93 = 29.03%**

Holdout:
- **24 / 96 = 25.00%**

## Corrected tag counts

### All 457 — overlapping
- TREND_ALIGNED: 210
- KALSHI_LAG: 178
- ACCELERATION_BURST: 121
- OTHER: 246

### All 457 — primary priority
- KALSHI_LAG: 178
- ACCELERATION_BURST: 24
- TREND_ALIGNED: 9
- OTHER: 246

### Validation primary
- KALSHI_LAG: 35
- ACCELERATION_BURST: 3
- TREND_ALIGNED: 1
- OTHER: 54

### Holdout primary
- KALSHI_LAG: 38
- ACCELERATION_BURST: 2
- TREND_ALIGNED: 2
- OTHER: 54

## Guardrails / interpretation

- No threshold was selected or changed from this audit.
- No +5/+10/+20, protected-exit, future PATH or economics field was used in blocker/funnel calculations.
- Uniform boolean rates are properties of the current serial candidate universe, not claims about all 15-minute BTC market states.
- Historical/holdout findings are descriptive only.
- Any regime-aware signal change must be defined separately and tested on contracts after a fresh prospective cutoff.
- Coverage Rescue V1 and Economics Forward V1 remain independent and untouched.
