# BTC15 recovered ladder state and completion candidate

Candidate BTC15_LADDER_COMPLETION_20261003_V1. SIGNAL ONLY / NO ORDERS.

The Oct 3 RETAIN_NATIVE decision made zero strategy changes. It did not erase
earlier work. This release continues from the recovered implementations below.
Entry alpha is retained because the completed development studies rejected
expansion; product lifecycle and event evidence are completed separately.

| Work | Exact source | Implemented / promotion / disposition |
|---|---|---|
| EARLY V4.7 tournament | MAIN abe212b513827c8cec28a2f64e0161e79296bd82, bot blob f547ab4238592910ed76fee61870cd18714d09f0, lines identified by V4.7 entry section | Coded and in native lineage; unchanged 45c,75%,8pt,2–10m,$25. No FINAL veto, persistence or strengthening requirement. |
| EARLY research logger | Same file `_candidate_flag` | Separate 20pt/4–10m research flag, not the actual entry gate. Candidate journals genuine entry decisions and does not call this flag an accepted origin. |
| EARLY tier expansion | fb1ff533811230b300af17e30dd0e91b1bb051ae, research_review/early_coverage_ladder_v1_20260921/REPORT.md | Coded research; no stable high-coverage ladder. A no calls; B/C failed September evidence. No live promotion or reversal of rejection. |
| EARLY/SCALP finishline | 543e7d960f1b8aeb9f7c7de2645f46d5b1e181ab | Both single-hypothesis development screens failed; no thresholds retuned. SCALP filter retained only 25/53 origins and 23/41 winners. Not promoted. |
| Later EARLY T1–T7/base/persistence/preemptive families | BTC15_EARLY_Value_Entry_Research_Report.pdf; Oct 3 Ladder Analysis package | Research-only selections rejected. T7 15/47 and T1 28/84 overall descriptive results do not support 85% entry reliability. No final-validation tuning or repeat study. |
| FINAL V4.6 + BRTI | MAIN frozen bot and embedded BTC15_DASHBOARD_STATE_V2.py | Coded/current. Strong core retained, including exact target/BRTI alignment and 5s freshness. Dynamic publication uses the existing corrected native fair result, not startup-only `_two_final_*` globals. |
| FINAL MIXED delay/clearance | main score_final_mixed_delay_recheck_v1.py (blob b7920f818824cb5378f128bd130b8d1d899797f7), score_final_mixed_45s_union_impact_v1.py (fa28c81357f9522e9469faa9eae5978018886468) | Coded research, not live rules. At-least45s differs from clear-within45s; 22/22 is in-sample selected, clear-within45s is 21/23. No delay added. |
| Full directional manager | 750cd2298d21405aa51987d32f232779ae71d294, BTC15_DIRECTIONAL_POSITION_MANAGER_V1.py blob ccb4cfa8f61abb90f81ebb87b7bd24646af219e9 | Coded offline, absent from MAIN. 36 original tests. Reused byte-for-byte; no enabled severe EXIT rule. |
| Later EARLY-only authority reducer | local lifecycle candidate dcc44cc858eb745953c48860bbe1e2e847860326; recovered preserved source in 9aa9ebf569c559a1e5daf7e8654738cfd7e957f8, btc15_directional_signal_authority_v1.py blob 693f87cddc41de58d59088ea67a921db0861406f | Coded offline. Removes manager's extra FINAL entry veto, suspends on missing BRTI, preserves immutable origin and PROTECT. Reuse pure reduce_signal/encode/decode, not the old synchronous HTTP/SQLite architecture. Earlier isolation blocker was infrastructure, not evidence rejecting its directional semantics. |
| Tiny alternate manager branch | e99dede1ba7e1c0119d3f487e3651d0e3b6e15b2 | Separate abbreviated shadow implementation; not substituted for the full tested reducer. |
| Native true-SCALP/profit shadow | MAIN frozen bot `_maybe_true_scalp_signal`, `_update_profit_shadow` | Already coded/current independent shadow; preserved. Historical 76 origins are not current V8.1 qualification; no promotion of shadow exits. |
| V8.1 current detector | b05723ec622f901a05402ecf27f4d33505753ef1; v81_30_45_live_feed.py blob e18f07377cbd53adfdb77d1e60ff8d3db4c901a5 | Coded/current service. Entry/confirmation/cooldown/reentry/180s loop AST unchanged. Only detached publication journal plus read-only route added. |
| V8.1 exit lifecycle hypotheses | fb40269fb3cb973deb3f987899dd466a3da287cc (PR26 merged); completion_audit/v81_exit_candidate.py | Coded offline, merge did not enable exits. 180s,5/2,10/4,8/10 hypotheses not selected. No exit optimization against viewed results. |
| Serial/reversal/reentry | b124c54ea9d015d88c5237d5e0bc45ded8a37f36, shadow_diagnostics/scalp_reversal_reentry_ladder_v1.py; later finishline and Sep29 SCALP review | Coded research; later 103-origin ownership includes unarmed retirement, not an exit. 5/4 has giveback overshoot and unresolved armed origins. No live promotion justified; no recreation. |
| Watch/exit warning research | 7d5bc7cfce61fb0ee1d2c67fc67c04ed096f212a, SCALP_WATCH_EXIT_WARNING_V1_FREEZE.md | Predeclared shadow work, not proof of predictive EXIT authority. Retained as research. |
| 5M/3M/flip risk | PR38 229da5f5ac1b7c975df1f6fb07e61e66f5331083, merged and included in MAIN; btc15_information_v1.py | Already implemented. Candidate surfaces native-cycle countdown bands and existing model probability; no new predictive calibration or exit trigger. |

## Exact release behavior and diff

The frozen native bot/model bytes remain unchanged. The original quote consumer
adds a constant-size witness of the same accepted quote it already returns.
The native launcher submits one small complete decision per original evaluation
to a bounded product worker. No fast informational frame creates action events.
The worker consumes recovered EARLY-only lifecycle semantics, durably commits
the event and checkpoint, and serves only an expiring JSON projection. HTTP
reads create no transitions. The original cohort is not rewritten or rescored.

New product events record official open/close/ticker/target, original EARLY ask,
native epoch/sequence, model fingerprint, BTC source/receipt, accepted quote
identity/time, BRTI source/receipt and publication-derived FINAL linkage.
Existing complete BRTI closeouts are copied to the new journal as settlement
records; absent closeouts remain missing. V8.1 journals its exact immutable
signal and only strictly later same-side accepted bids. It records observed
MFE/MAE and +8/+10/+15/+20/+30 versus -10 chronology, gaps, horizon and movement
states. These are gross observed quote deltas, not fills or selected exits.

The journal uses one 16-item nonblocking queue and one disk worker per service.
SQLite records are compressed, bounded to 30 days/300,000 rows, with a 512MiB
database limit. Retention starts are exposed. Errors disable guidance; native
polling never waits for journal I/O. This is a product journal, not a generalized
recorder or a claim of physically zero scheduling cost.

## Comparison with baseline

| Dimension | Candidate versus baseline |
|---|---|
| Entry frequency, price, directional reliability | Same entry predicates. No numerical increase claimed. Actual events now distinguished from the stricter research flag and linked durably. |
| EARLY price/timing | <=45c retained, <=50c target and25–35c ideal shown; actual2–10m gate retained. |
| FINAL timing/coverage | Same strong core; no45s delay. Current native probability/state publication retained per decision. |
| FINAL protection | Previously missing production origin linkage is explicit; confirmation/lost confirmation/opposition feed recovered latched PROTECT. Missing data is UNAVAILABLE, not a warning. No unsupported numeric EXIT. |
| SCALP frequency/execution | Existing V8.1 detector unchanged. Original ask/later bid and target/stop order become recorded. No new target/stop strategy claimed. |
| PASS/missing | Failed numeric entry conditions recorded. Source gaps, outages, restart intervals and incomplete paths remain distinct from observed PASS. |
| Integrity | Same BRTI5s requirement; accepted quote and source clocks retained; read-time expiry. Signal-only/no orders. |

The earlier reviewed cohorts cannot supply an honest current-build frequency or
accuracy estimate, so none is invented. This bounded mission selects B for new
alpha and completes the specific recovered lifecycle/journal product work.
Live operation, after functional checks, will accumulate current performance.
Both failed Oct3 Ground Zero intervals remain excluded from all uses.

## Focused verification

61 local functional tests passed, including the36 original manager controls.
Coverage includes immutable origins and restart, no FINAL entry veto, timely
FINAL, opposition/protection latch, source future/staleness rejection, exact
quote ask binding, journal readback/hash/expiry, UP/DOWN target/stop ordering,
duplicate quote rejection and missing horizon without an invented exit fill.
Generated Python runtime compiles. V8.1 detector and loop AST match the frozen
baseline. These tests prove mechanics, not market performance. Hosted and live
results must be appended only after they are observed.
