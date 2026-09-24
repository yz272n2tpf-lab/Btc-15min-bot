# BRTI publication expiry: engineering checkpoint

Production remains frozen at `3e552065e34a0a402bc3ca4598b57dff1f1c6e77`,
Railway main deployment `f82466d0-70ab-4779-a0fd-58832ad31513`.
No code/configuration/model/threshold/weight/secret/service or deployment changes
were made to production. SIGNAL ONLY / NO ORDERS.

## Result and limits

The dominant failure is the five-second **complete-decision publication cadence**,
not a failure of original decision-time BRTI qualification. The retained dashboard
frame contains the original decision's BRTI. Its absolute expiry remains true
source time + 5 seconds, even when the owner and main's background receiver have
newer data. Refreshing the API does not reevaluate that decision.

The 2026-09-24 20:15–21:15 UTC validation-only window was used only for this
infrastructure timing diagnosis. No outcome, entry price, model probability,
predictive parameter or ladder selection was used by the new diagnosis tool.
The <=17:00 development evidence and all holdouts were left unchanged.

| Observed quantity | Result |
|---|---:|
| Original decisions with fresh, causal BRTI | 668 / 668 |
| Fully qualified observer instants | 1,504 / 3,600 (41.7778%) |
| Retained BRTI expired, other observer gates usable | 1,754 |
| Of those, within normal <=5.181s snapshot retention | 1,731 |
| Of those, longer retention after a logged quote WAIT | 23 |
| Other quote/parity waits | 237 |
| Rollover prior/no-current contract observations | 105 |
| Distinct decision frames observed after BRTI expiry | 649 |
| Owner fresh sampled observations | 3,600 / 3,600 |
| New owner successes / errors / 429s | 1,573 / 0 / 0 |

These are observations at one-second intervals, not continuous availability.
Existing validation evidence established maximum sample gap 1.017684 seconds.
The 23 longer-retained frames coincide with quote waits already logged before
the observation; they must not be presented as delivery failures.

## Timing decomposition

| Stage | Median | Observed range |
|---|---:|---:|
| Source timestamp to first main receipt | 1.329s | 0.270–2.304s |
| First main receipt to decision | 1.250s | 0.004–2.997s |
| BRTI age at original decision | 2.486s | 0.610–4.478s |
| Decision to main qualification check | 0.00553s | 0.00139–0.18826s |
| Decision to first sampled API response | 0.576s | 0.241–1.420s |
| Next decision within the same contract | 4.999s | 4.810–5.181s |
| Expiry gap before next same-contract decision | 2.486s | 0.611–4.481s |

The first sampled API response includes the observer's sampling phase; it is
not a measurement of server publication latency alone. The source-to-main
measurement combines source age at the owner, owner request timing, local
poll phase and transport. The stored evidence does not contain owner HTTP
completion times or every one-second main receipt. Those individual components
cannot honestly be separated further. Owner observer receipts are not main
receipts and were never substituted for them.

The owner advances every 2–3 source seconds in these samples. Its code schedules
the next successful fetch two seconds after completion; main reads cached owner
state independently each second. The strategy/data loop publishes a complete
decision about every five seconds. The dashboard rebuilds from paired unified
rows, preserving their source decision timestamp and original BRTI age.

Example: source 20:15:44.000, main receipt 20:15:45.191375, decision
20:15:46.668321, absolute expiry 20:15:49.000. At observer receipt
20:15:49.105713, that retained value is 5.105713 seconds old and correctly fails
freshness. The next complete decision is 20:15:51.678858. A later owner value
cannot be lent to the 20:15:46.668321 decision.

## Engineering bound and rejected shortcuts

For original decision `d`, causal source `s`, receipt `r`, and next decision
`d_next`, require `s <= r <= d` and current age <=5 seconds. The inevitable
expiry gap is `max(0, d_next - (s + 5))`. With five-second decision spacing,
every positive source age creates a gap. Faster browser polling, republishing
the same frame, or changing `generated_utc` cannot alter that deadline.

An explicitly **non-causal, unattainable upper-bound calculation** grants
instantaneous access to every observed owner publication at its source time,
instantaneous main publication and removes all quote/parity waits, while keeping
the actual decision timestamps. Even that bound qualifies only 2,232/3,600
observer instants (62.0%) for this observed owner-publication stream. This is
not a replay result, candidate forecast, recovered validation observation or
performance claim. A different owner publication stream has a different bound.

Replacing retained decision BRTI with newer receipts fails causal checks.
Increasing local owner-read frequency cannot remove the fixed-decision gap.
A blind `POLL_SECONDS = 1` change would create new complete decisions, but it
also feeds more rows into existing rolling history and sample-count diagnostics.
Executable tests against the actual production functions demonstrate seven
versus 31 persistence observations in a 30-second window and different rolling
extrema for the same underlying timestamped path. Persistence here is telemetry,
not evidence that a primary ladder currently uses a persistence threshold.
Rolling extrema are inputs to the existing scalp shadow feature path.

Consequently, no candidate was certified as preserving the requested strategy
behavior. **The bottleneck is not proven physically irreducible; it is
irreducible for the retained frames under the existing decision cadence.**
No deployment-ready runtime correction is claimed.

The next architecture choice is faster **new complete decisions**, each with
its own actual timestamp and causally available inputs, while explicitly
preserving or revalidating cadence-dependent history, event and sampling
semantics. Merely updating BRTI inside an old decision is prohibited. A design
that decouples publication and historical-state sampling needs equivalence
tests at the legacy decision cuts, provenance tests for new cuts, source/quote
WAIT tests, and load/retention testing before any release. It must not silently
turn a transport correction into a different strategy sampling policy.

This is the outstanding behavior/cadence decision. Production remains frozen;
no new prospective cohort boundary was created. No before/after improvement
is available: baseline publication availability remains 41.7778%, original
decision-time causal freshness remains 668/668, and any future corrected-runtime
availability must be measured separately from ladder performance.

## Verification

`python -m unittest test_btc15_brti_delivery_v1
test_btc15_brti_history_recovery_regressions test_btc15_independent_btc_history
test_btc15_publication_expiry_bound -q` passed **55 tests**.

This includes the actual production delivery/closeout/history functions and new
expiry, repeated-publication, jitter, transport failure/recovery, owner restart,
future-receipt and cadence-coupling tests. Quote-interruption/rollover history
preservation remains covered. The full production regression suite was not
rerun because no runtime correction was produced or promoted; the prior PR36
238-test release evidence is not represented as a test of a new candidate.

The production core, delivery helper and embedded dashboard installer copies
were verified byte-for-byte against GitHub blob identities:

- core: `f547ab4238592910ed76fee61870cd18714d09f0`
- delivery: `0bc0237312e2c0efb2e86630e2bcc9ef3f6e89e7`
- dashboard installer: `e1f1390f1fbf6d6649f7dfc319f5b085a9676afd`

Owner deployed commit `37735e737690096edea31beb2faff6842770ac4f` has the same
owner-file content as the inspected main release tree. Connected Railway status
still reports main/owner/clean SUCCESS at the previously frozen deployment IDs.
Main /data remains 10 GB; clean /data remains 50 GB.

Input SHA256 identities and exact aggregate timing values are recorded in
`BRTI_PUBLICATION_EXPIRY_DIAGNOSIS_20260924.json`. Narrowly fetched quote/target
WAIT log evidence is in `BRTI_PUBLICATION_EXPIRY_WAIT_LOGS_20260924.json`.

## Remaining ladder bottlenecks (existing evidence only)

- EARLY: separate fresh-input availability from model rejection of cheap sides.
  Cheap selected-side opportunities remained scarce; the observed <=50c cases
  failed fair/gap requirements. No threshold change or prospective benefit is
  justified by this infrastructure diagnosis.
- Core SCALP: executable ask/bid identity, stop-first chronology, spread/fees,
  and unconnected position lifecycle remain material. Excursions are not fills
  or realized profit; both-direction acceptance remains open.
- V8.1: candidate-to-qualified conversion is blocked by its existing impulse/
  quote-lag/base structure, with no qualified entries in the frozen window.
  Faster main BRTI publication alone cannot establish connected exit behavior.
- FINAL: clean call count is too small for the 93–95% objective. With no EARLY
  entries, confirmation/profit-protection lifecycle effectiveness is unmeasured.
  Warning states must not automatically be scored as exits.

No broad ladder tuning, validation reuse for model selection, or waiting for
elapsed prospective time was performed.
