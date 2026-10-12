# Frozen offline EARLY candidate

Research baseline: 5c856bd15824a929a5dee04b77cde65f50b4f602.
Preserved original workspace: candidate/early-directional-recovery-20261011 at
20502c26566f6279e74d4889dd940f53a3cc77f8. Neither is a fresh production identity.
Design reference: Redesign EARLY Buy Ladder.pdf, Library identity
libfile_4b621627b28c8191a5f15f76f1c70d92, read completely before implementation.

## One architecture and rationale

Both sides use the same delivered snapshot and independent signed BTC/BRTI
short movement. Model-preferred-side selection, 75% settlement probability,
positive target gaps and model-minus-ASK admission are removed. The retained
research demonstrated target/prediction mismatch; no replacement probability
threshold is invented. Settlement probability remains labeled and available to
unchanged management only. Target alignment classifies continuation versus
pre-crossing (including mixed/at-target, separately labeled in features).

The 30s causal lookback, 0.10 times observed range minimum impulse, 0.30 path
efficiency, material quote-reversal check and 10s advancing-observation
confirmation are retained provisional directional hypotheses, not validated
predictors. BRTI gets its own reflected path-efficiency check at the same 0.30
boundary, requiring two streams to corroborate movement. Acceleration,
movement persistence and long context are exposed without fitted coefficients.
No completed two-minute trend or prior BID rally is required for primary-range
recognition. No return result will be used to retune these settings in this run.

Recognition is WATCH and has no ticket or entry side effect. A setup has an
immutable identity until at least 30s of observed adverse BTC/BRTI short movement
establishes a genuine reset. Outages clear confirmation, never reset identity.
A fresh ticket can be requalified for the same unfilled setup after fresh 10s
confirmation; predecessor and sequence preserve the distinction from a new setup.
No new setup is manufactured when price temporarily leaves/returns to the range.

## Opportunity quality (one unestimated approach)

Q = expected net resale cents conditional on valid delayed entry under the
unchanged baseline condition-exit policy. Its outcome is the first admissible
observed same-side BID after condition EXIT plus 10s exit reaction, minus the
refreshed entry ASK, both fees, and an execution reserve. Never use future maximum
BID, model fair value, eventual settlement, payout capacity or probability minus
ASK. Inputs/support boundaries: side, continuation/pre-crossing and mixed
location, short noise/efficiency/persistence, quote spread, price group, remaining
runway, exact source/feature bindings, entry/exit latency and management identity.

No fitting is performed. Missing original execution receipts, validated depth,
fee applicability and untouched evaluation prevent defensible conditional
calibration. Mean, lower uncertainty bound and downside estimate are explicitly
null. Authorization requires supported uncertainty and downside by the specific
context/price/runway, not broad direction means. No trained artifact exists.
Synthetic support is an explicit constructor switch restricted to rows labeled
SYNTHETIC_FIXTURE; it tests state transitions without inventing historical scores.
All outputs still have signal_only=true, orders=false, production_enabled=false,
actionable=false. There is no production trust registry or activation switch.

Primary 25–55c entries require every gate. Sub25 has no hard floor but also needs
120s favorable context and no adverse increment in either short BTC/BRTI path,
plus its own currently absent economic support. 56–58c needs separate currently
absent exceptional economics. Above58 is rejected. All exceptions remain
historically ineligible. Their stronger directional rule is a provisional
safeguard, not demonstrated special predictive support.

## Time, execution and ownership

Historical lookback: 30s, optional 120s context. Algorithmic confirmation: 10s
in delivered advancing observations. Publication delay: actual received minus
source time. Manual reaction: 10s from ticket/observational-qualification
availability. Exit reaction: separate 10s after EXIT availability. Observation
tolerance: at most another 10s, reporting exact elapsed time. Entry runway:
remaining after publication delay > 180s development room + 10s manual + 10s
exit budget. 180s is provisional coverage, not an estimated optimal runway and
never an automatic exit. No 4/5/6/7-minute selling timer exists.

Price/source/evidence revalidation is continuous on advancing input; tick(now)
expires tickets even without publication. This is an offline API, not a running
scheduler. A future caller would have to drive tick; no collector is started.
Actual native source validity delegates to unchanged qualify/quote/feature
validators, checking exact frame-to-row binding. The retained native schema has
no validated depth adapter and cannot pass liquidity authorization. Observed
historical rows can support diagnostics but cannot become verified native frames
through displayed freshness flags.

Manual confirmation is an explicit event with current ticket, same contract and
side, refreshed observed ASK, positive quantity, event ID/time and elapsed
reaction check. It records a user declaration, not a verified broker fill.
Invalid confirmation is rejected. Reports of an already executed unqualified
trade would require a separately designed recovery/import event; none is inferred
here. Confirmed origins are immutable. EXIT is guidance, never automatic closure.
Explicit closure is necessary before another confirmed entry; same setup still
needs genuine reset if already consumed. No adding/hedging/reversal/netting.
If opposing candidates simultaneously qualify, neither gets a ticket.

Explicit simulations use separate origins, cannot be promoted to real positions,
and never block recognition or ticket assessment. They may coexist as labeled
counterfactual paths. They are not a sequential portfolio simulation.

## Management and protection

CoreEngine.manage is imported byte-for-byte from the baseline. Its warning,
recovery, structure-break, settlement, data-unavailable and condition-exit
semantics remain unchanged. Native early_management.decide is also unchanged.
Native FINAL qualification is read through protected_frame unchanged; previously
established strong FINAL loss or qualified opposition latches PROTECT as in the
existing authority layer. This is unavailable on retained normalized observations
and is reported as such, not reconstructed from p alone.

Pre-crossing compatibility is mechanical: positive approach can remain supported
without a forced EXIT; adverse corroboration still exits. After a pre-crossing
warning, baseline recovery requires positive gaps, so WATCH can persist until
crossing despite renewed progress. This conservative limitation is retained.
No management-rule adaptation or weakened protection is selected.
Internal HOLD/WATCH/PROTECT map to public WATCH with stable/weakening labels;
internal EXIT maps to EXIT. Ticket cancellation never creates an EXIT.

## Evaluation, frozen before results

Use exactly seven retained, whole-contract chronological groups: September26–27
122; September28–29 82; October4 16; October6 24; October7 24; October8 24;
October11 4. Check no overlapping contracts. Total expected296 contracts,
48,628 observations. The previous268 is a subset, not additional independent data.
All were exposed before this assignment; none is an untouched holdout.
Reuse September timing-defect, October native prediction/binding, original price
comparison/gate/lifecycle and BUY/EXIT/visibility conclusions; no reconstruction,
model tournament, full-journal retrieval, shadow or prospective wait.

Compare unchanged unified-value baseline with one redesigned candidate on identical
retained inputs, 10s delayed entry/exit and the same conservative fee/reserve stress.
Baseline proposals are not qualified economic tickets. New metrics separate
recognized setups, algorithmic confirmation, primary-price observational
qualification, delayed cancellations and explicit diagnostic simulations.
The diagnostic deliberately bypasses source/economic gates ONLY to measure
hypothetical paths; it never creates a research BUY ticket. Exception groups
cannot enter these scenarios. Each setup gets one first qualification/recheck,
no best-entry search and no repeated attempt after cancellation.

Use only actual observed quotes. Gaps >15s/epoch changes and unhealthy paths
invalidate pending entry or censor outcomes. Incomplete, canceled, no-EXIT and
missing delayed quotes remain separate. Complete-only net scenarios are exposed,
correlated and informatively censored. Report descriptive distributions and
contract counts; no independent profitability confidence interval is justified.
No fitting, tuning, model selection or alternative management trial after results.
