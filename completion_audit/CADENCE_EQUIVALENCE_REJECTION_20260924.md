# Faster complete decisions: rejected engineering prototype

**Decision: REJECTED; not deployment-ready. SIGNAL ONLY / NO ORDERS.**

Production oracle remains `3e552065e34a0a402bc3ca4598b57dff1f1c6e77`, tree
`586f8cfd635d6ed817c63202cdec0b8bcc454e0c`. No production code, configuration,
weights, thresholds, source limits, credentials, services or evidence changed.
No deployment boundary was created. Existing rollback remains intact.

This continues the publication-expiry checkpoint on
`audit/brti-publication-expiry-20260924` (`c3cd548d42ef762daedee74f48b01323834bbc32`).
Its diagnosis and 55 focused checks were not repeated. No prior replay,
validation scoring, ladder search or packaged payload was rebuilt. The packaged
display-gate expressions were read in memory solely as an unchanged oracle.

## Design tested

Two clocks: the existing loop remains the sole committer of strategy history and
lifecycle state; extra one-second decisions project from its retained history
using genuinely causal current inputs. Legacy commit timestamps come from the
existing loop, including its jitter and skipped quote-wait iterations, rather
than a newly rounded grid. Additional projections must never add persistence
hits, minute-candle samples, extrema history or cooldown transitions.

Implemented an isolated-history research prototype and adversarial probes under
`completion_audit/cadence_projection_probe_v1.py`. It has **no runtime hook**.
It was deliberately not connected to production after the complete-path gate
failed. A successful standalone history container is not a release candidate.

## Acceptance result and counterexamples

30/30 new engineering tests pass **as tests of guarantees and rejection
counterexamples**. They do not mean complete semantic equivalence passed.
Command: `python -m unittest test_btc15_cadence_projection_probe -v`.

1. **Actual emitter phase: persistence changes despite no extra append.**
   `log_unified_subminute` counts before appending its current legacy sample.
   With unchanged qualifying UP inputs at times 0 and 5, the actual emitted
   count at 5 is 1. A projection at 6 from the committed anchor counts 2,
   despite appending zero micro rows and receiving no new market information.
   Protecting the writer alone therefore does not establish equivalence: the
   original pre-append evaluation phase must also be preserved. Isolated
   as-of-history counts are not identical to the original emitted count.
2. **Exact deployed parity audit: five-second PASS becomes one-second WAIT.**
   The consumer captures the complete CSV frame at synthetic time 300. Its
   independent BRTI reference read finishes at 302. An intervening publication
   replaces the single quote-proof file at 301. The proof is now for a different
   decision identity. The actual `audit()` plus actual quote `replay()` rejects
   it. Both schedules have identical prices, ticker, target and BRTI publication;
   clock, target, quotes, BRTI time and BRTI value deltas all equal zero.
   The frozen five-second schedule still holds the correct proof and passes.
   This is a **synthetic concurrency counterexample**, not a newly measured
   production incident. WAIT is correct; weakening the exact-frame join would
   be an unacceptable workaround. Isolating in-memory strategy history does not
   solve this publication/provenance delivery problem.
3. **Committing extra lifecycle evaluations changes state without new prices.**
   The actual profit shadow starts with entry ask 30c and an unchanged 51c bid.
   At the first evaluation it arms and returns. The next evaluation recognizes
   TARGET_20. Five-second evaluations exit at relative time 5; one-second
   evaluations exit at 1. This reproduces in both directions. No new price
   observation is responsible. Keeping this routine on the original clock
   preserves this subsystem, and that narrow workaround is also tested.
4. **Discarding projected state is not proof of connected lifecycle behavior.**
   If an extra projection emits a new entry but discards all pending state, its
   following projection has no entry to protect. This is a design failure mode,
   not a claim that the existing Core display already has connected exits.
   New micro-entry event ownership and downstream consumers need an explicit
   tested contract before calling this a complete decision architecture.

The prototype therefore fails end-to-end equivalence. Per Eric's instruction,
it is rejected and engineering stops here. Full release regressions and hosted
release CI were **not** run: their prerequisite semantic gate did not pass.
No model retraining or predictive parameter selection was attempted.

## Cadence-dependent inventory

| State / feature / gate | Dependency and required preservation | Status in this probe |
|---|---|---|
| Main `cycle_start`, `POLL_SECONDS`, exception sleeps, `iteration` | Original iteration instants, quote/no-market waits, 30s heartbeat and state-save cadence; extras must not shift or become legacy commits | Timestamp-level simulation only; real scheduling/load equivalence unproven |
| `history`, active ticker | One retained original-loop row; clear contract-local history on exact rollover; 240s retention | Isolation, skipped/jittered anchors and contract reset tested |
| BTC/ask deltas 5/15/30/60/120s | Last original sample at or before cutoff, not the Nth most recent faster row | Original timestamp lookup retained in design; no full fitted-model replay claim |
| Ask low/high 30/60/120s, bounce, drawdown, ask-position | Extra extrema must not leak into subsequent legacy features | Actual extrema function tested against isolated transient extreme |
| `_ec_btc_ticks` / `_fair_btc` | Preserve pre-open BTC during quote waits; actual source/receipt clocks; 20min retention; completed candles available at bucket end; partial OHLC only original retained ticks plus causal current input | Required, not modified; full projection/fair-path equivalence not completed after rejection |
| Fair features | elapsed/remaining, current side, target distance/absolute/percent, move from start/percent, moves and supports 1/2/3/5min, range5, vol5, distance per remaining minute, distance/range | Definitions and immutable model untouched; elapsed-time changes must be distinguished from new prices |
| Fair forest/sigmoid, feature order, clipping, weights | Exact artifact and weight identity; no extra fit or revised feature interpretation | No replacement or prediction-equivalence claim |
| `_early_hist` | 90s retention; 30s persistence includes the current **legacy** row; fair/ask slopes 5/15/30s; no extra append from projections | No inflation, inclusive boundary and expiry tested |
| `_unified_hist` | 180s retention; contract/side-specific 30s count computed before original append; fair slopes 5/15/30s | As-of count function matched on original timestamps, but original emitted pre-append phase **fails equivalence** |
| Broad/provisional candidate flags | Original threshold expressions; repeated samples cannot accumulate extra hits | Synthetic persistence checked; no threshold changes |
| Lag15/30 and reversal PUSH/PULLBACK/REVERSAL_WARN/AGAINST/MIXED | Original side-aligned BTC and quote slopes and history windows | Required, untouched; complete projection equivalence unproven |
| EARLY raw display gates | Existing ask/fair/edge/time/gap limits; original <=45c gate retained, no replacement <=50c gate | Exact deployed expressions exercised with fixed-output fixtures |
| FINAL raw display gates | Side agreement, <=8min, 6min gap change, fair/range and BRTI authority | Exact expressions; 8min, 6min and five-second boundaries checked |
| Core SCALP raw display gates | Original ask/fair/edge/time/gap limits | Exact expressions; current causal quote changes distinguished from sampling |
| `pending`, `last_event_created`, event IDs | 15s entry spacing; ask entry, subsequent bid path, horizon/rollover, max/min, stop-first barriers; one original update before new events | Must stay original clock if retaining original sampled-path semantics |
| `_true_scalp_pending`, `_true_scalp_last_signal`, features/model/medians | Original 120s cooldown, entry timing, min time left, ask ceiling, threshold, 180s horizon, stop-first outcomes | Actual pending update tested; fast new-price stop/recovery changes are causal information, not equivalence |
| `_profit_shadow_pending` armed/arm_ts/peak/finished | Arm-on-one-evaluation then later target/trail/BRTI/horizon evaluation | Actual unchanged-price failure reproduced for UP/DOWN; legacy-clock guard tested separately |
| FINAL protection process active/trigger/last source | First qualified frame fixes side/fair/gap/bid; later frames produce deterioration telemetry; new source timestamps change which rows it processes | Downstream ownership/filter integration not proven |
| Late caution/guard and protection displays | Existing source-time/remaining-time semantics; warning is not automatically an exit | Untouched; must not advertise additional connected behavior |
| BRTI delivery states/statuses/seen/owner epoch | Original source and local first receipt; select received <= cut; age <=5 at cut **and** check; error/recovery/epoch isolation | Every qualified simulated projection checked; restart, errors, jitter and recovery covered |
| BRTI final60 / pending closeouts / conflicts/finalized sets | Count actual distinct upstream source seconds, causal history visibility; independent 600s recovery, no fabricated seconds | Original implementation untouched; extras must not advance closeouts |
| Staged market / official open-close / fixed target | Discovery and handoff authority remain on original path; no new ticker or target inferred by a projection | Quote replay rollover/close rejection tested; live integration not attempted |
| Quote provider book/seq/epoch/consumed clock and proof file | Contiguous timestamped book, exact frame identity, no duplicate-source freshness renewal | Actual parity interleaving **fails candidate acceptance** |
| Paired UP/DOWN CSV publication; BRTI/model-input journals | Both rows, quote proof, BRTI receipt and feature vector must identify one complete immutable decision; no old cut relabeled | Atomic publication integration absent; cannot claim end-to-end source qualification |
| Dashboard/observer source age, BRTI age, parity age; bounded CSV tails | More rows shorten time represented by byte limits; independent read/update schedules must not pair different frames | Existing readers retained, projection impact not proven |
| V8.1 independent impulse/history/persistence/cooldown/exit state and 3.5s publication gate | Its separate owner/quote/call clock must stay unchanged; main extras must not be interpreted as duplicate V8.1 persistence hits | No V8.1 changes or performance claims; interaction integration unproven |

## Quantitative availability: isolated BRTI bound only

Synthetic one-second source publications, original causal receipt timestamps,
0.1s observer spacing, 90s run with 20s warmup removed: **700 scored instants over
[20,90) seconds per configuration**. No market outcomes or historical validation
rows. All qualified values were received by their decision and <=5.0s old at
the observation. Inference cost and independent parity delivery are omitted.

| Synthetic scenario | Five-second publication | One-second projection |
|---|---:|---:|
| 0.4s source-to-receipt delay | 574/700 (82.0%) | 700/700 (100%) |
| 1.4s delay | 434/700 (62.0%) | 700/700 (100%) |
| 2.4s delay | 294/700 (42.0%) | 700/700 (100%) |
| 4.4s delay | 14/700 (2.0%) | 70/700 (10.0%) |
| 1.4s delay, +/-0.2s publication jitter | 420/700 (60.0%) | 700/700 (100%) |
| 1.4s delay, eight-second transport failure | 376/700 (53.7%) | 614/700 (87.7%) |
| 1.4s delay, eight-second quote interruption | 372/700 (53.1%) | 620/700 (88.6%) |

These are **source-only engineering bounds**, not expected production gains,
full source-qualified availability, trading performance or continuous observed
availability. The previously supplied 41.8% prospective measurement is neither
retuned nor substituted into these synthetic cases. Since complete parity
fails, **no deployable before/after availability improvement is established**.

## Raw ladder differences, kept separate

Exact deployed display expressions with synthetic fixed model outputs:

- Repeated identical inputs: zero differences across EARLY/FINAL/Core SCALP.
- New causal ask 40c -> 80c with corresponding edge: EARLY and Core turn off;
  FINAL stays on. This is quote information, not a persistence change.
- New causal BRTI UP -> DOWN: only FINAL turns off in the raw expressions.
  Full qualification still requires all original source gates.
- Crossing 8min or the existing 6min FINAL gap boundary changes gates through
  their original clock semantics. This is explicitly a time-boundary effect,
  not evidence of a newly observed price or an extra persistence hit.
- A newly observed bid stop followed by recovery changes sampled stop-first
  outcomes; the actual Core shadow updater reproduces that causal difference.
- The unchanged-book arm/exit difference above is instead evaluation-count
  dependence and fails equivalence unless its state clock is held fixed.

No actual fitted-model EARLY/FINAL/Core/V8.1 output-equivalence or performance
improvement is claimed. The fixed validation-only cohort and untouched holdout
were not loaded by these probes. No predictive selection occurred.

## Checkpoint for Chat

Do not deploy this prototype. The next engineering prerequisite is a complete
immutable frame handoff: matching quote proof, paired quotes, causal BRTI and
model inputs must remain available to independent readers for that exact frame
without borrowing a later proof. That must be combined with explicit legacy
state clocks, original pre/post-append evaluation phases and tested ownership
of any newly emitted intraperiod events.
Then rerun end-to-end semantic acceptance before full release regressions.
This is a required direction, not a proven impossibility of all faster designs.

Stop here under the user's rejection rule. No broad ladder tuning, release
promotion, deployments or elapsed-time waiting follows this checkpoint.
