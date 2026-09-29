# BTC15 SCALP Round 2 — exact capture requirements

Research specification only. No collector, production, model, admission policy or strategy is modified. Preserve SCALP independence from EARLY and FINAL. Capture identities and clocks when they actually exist; missing values must remain null with an explicit reason.

## 1. Run and immutable policy manifest

`schema_version`, `capture_run_id`, `observer_epoch`, `producer_instance_id`, `producer_epoch`, `service_id`, `deployment_id`, `git_commit`, `source_module_hashes`, `model_artifact_hash`, `training_dataset_hash`, `training_cutoff_utc`, `policy_id`, `policy_hash`, `policy_constants`, `lane=SCALP`, `mode=SIGNAL_ONLY`, `orders_enabled=false`, `official_contract_universe_manifest_hash`, `partition_manifest_hash`, `run_started_utc`, `run_stopped_utc`, `capture_start_reason`, `capture_end_reason`.

Explicitly distinguish native true-SCALP, V8.1, generalized candidate research, legacy serial exit-only, later serial retirement and native T20/F6/TR4/BRTI. Record all eligible contracts including quiet contracts. Freeze chronological development/validation/final future blocks and any minimum signal/contract counts before outcomes are viewed. Do not label old records untouched holdout.

## 2. Immutable origin event

`signal_id`, `event_id`, `event_sequence`, `origin_hash`, `lane`, `contract_ticker`, `exchange_market_id`, `side`, `signal_generated_utc`, `signal_published_utc` if actually delivered, `signal_received_utc`, `original_ask_decimal`, `original_bid_decimal`, `price_unit`, `quote_id`, `book_sequence`, `quote_payload_sha256`, `quote_source`, `quote_source_utc`, `quote_received_utc`, `quote_consumed_utc`, `quote_validation_result`, `ask_size`, `bid_size`, `decision_id`, `model_evaluation_id`, `policy_id`, `model_hash`, `feature_snapshot_id`, `feature_payload_sha256`, `feature_availability_cutoff_utc`.

Preserve the actual published entry price as well as original observed market ASK. Retain the first quote received after publication/receipt, its identity and delay, and the existing V8.1 fresh-entry admission decision. Do not search later quotes for a cheaper ASK. The known 40c published / 57c observed class must remain rejected or unscored, never silently corrected into a new origin.

Record origin-time `signal_probability`, `signal_strength`, `seconds_left`, `elapsed_contract_seconds`, `btc30_aligned`, other actually used BTC/BRTI/features, validity masks, source IDs, history cutoff, and model-ready/gate results. Future quote and settlement fields must never enter this record or decide membership.

## 3. Official contract and executable quote path

`contract_ticker`, `official_open_utc`, `official_close_utc`, `official_window_witness_id`, `official_target`, `target_source_id`, `target_payload_sha256`, `side_mapping` (UP/yes and DOWN/no as established by the market), `quote_id`, `book_sequence`, `bid_decimal`, `ask_decimal`, `bid_size`, `ask_size`, `source_utc`, `request_started_utc`, `received_utc`, `consumed_utc`, `validated_utc`, `source_payload_sha256`, `source_contract_ticker`, `quote_status` and `rejection_reason`.

Keep the original event stream for both sides independently of which signals are active. An origin-to-quote link must prove the exact contract/side and strict later chronology. Capture source sequence continuity, heartbeats, expected cadence, stale/repeat/out-of-order events, intervals of dropped data, disconnects, reconnects, restart boundaries, and last-good quote. Do not interpolate missing quotes, infer best BID between samples, or turn subsequent ASK into exit. Timestamp granularity and clock error must permit a strict ordering conclusion. Capture a complete prespecified horizon even after protection so foregone later opportunity can be measured descriptively.

## 4. Every lifecycle transition, including non-exits

`lifecycle_event_id`, `event_sequence`, `signal_id`, `origin_hash`, `prior_state`, `next_state`, `transition_kind`, `trigger_reason`, `policy_id`, `trigger_quote_id`, `trigger_evidence_ids`, `evaluated_utc`, `published_utc`, `received_utc`, `remaining_seconds`, `current_same_side_bid_decimal`, `gross_unrealized_c_decimal`, `peak_bid_so_far_decimal`, `peak_gain_so_far_c_decimal`, `peak_quote_id`, `arm_threshold_c`, `armed`, `arm_event_id`, `arm_quote_id`, `arm_utc`, `arm_observed_gain_c`, `floor_c`, `trail_c`, `giveback_c`, `target_c`, `stop_c`, `exit_bid_decimal` when an actual exit guidance event exists, `exit_guidance_event_id`, `retirement_reason`, `unavailable_reason`, `origin_retained`, `lifecycle_policy_hash`.

`transition_kind` must distinguish SIGNAL, HOLD, TARGET, STOP, PROTECTION_ARM, PROTECTION_EXIT_GUIDANCE, SHADOW_PROTECTION_EXIT, RETIREMENT_UNARMED, RETIREMENT_EXPIRED, UNAVAILABLE and RECOVERY. A retirement is not an EXIT. A logged shadow comparison is not user guidance. An armed origin without exit remains explicitly unresolved/blocking under its existing semantics; no pre-arm stop or horizon exit may be invented.

For native BRTI protection retain every BRTI evaluation, not just BRTI flags at exit: readiness, side, agreement, selected source witness, stale/missing reason and the causal rule that triggered. Otherwise earlier BRTI exits and counterfactual policy replay remain untestable.

## 5. Serial / reversal ownership

`contract_ticker`, `signal_id`, `origin_hash`, `serial_index`, `prior_signal_id`, `prior_origin_side`, `lane_label` (FIRST/CONTINUATION/REVERSAL), `prior_terminal_event_id`, `prior_terminal_kind`, `prior_terminal_utc`, `elapsed_since_prior_origin_sec`, `elapsed_since_prior_terminal_sec`, `active_origin_ids_at_decision`, `overlap_allowed_by_policy`, `reentry_gate_result`, `suppression_reason`, `source_candidate_id`, `source_candidate_hash`.

Capture suppressed/blocked candidates too. A legitimate new signal gets its own ID. Continuation/reversal labels depend only on prior causally known origin/terminal events. Preserve same-side cooldown separately from cross-side blocking. State ownership must record SCALP exclusively; neither directional lane can overwrite or close it.

## 6. Admission, source witnesses and clock evidence

Respect b02577151b392c91e93d9f373e130ebfea89a594 and dcc44cc858eb745953c48860bbe1e2e847860326 unchanged. Preserve original detached common-journal gzip members, run manifest, actual member byte offset/length/sequence, member SHA256, authenticated acquisition route/principal, signed acquisition manifest and exact source/build/run bindings. Do not rewrite or recompress a member to pass it off as original evidence.

Where V2 exists, retain `BTC15_SOURCE_WITNESSES_V2` for quote/BRTI/BTC with `authority`, `clock_basis`, `owner_epoch`, `source_utc`, `received_utc`, `validated_utc`, `witnessed_utc`, `payload_sha256`; native/capture/model/build identities; genuine shared decision identity; official window and source/book payload witnesses. These are independent witness requirements, not values a researcher can generate retrospectively.

For each involved clock: trusted `clock_domain`, `clock_epoch`, reference UTC, validity interval, finite offset error bound, worst-case rate error, independent read error, health/step status, paired unshifted UTC and suspension-aware elapsed-time sample, certificate ID/hash. Preserve source/generation/request/receipt/decision/publication labels and original certificates. Never derive a BRTI source timestamp from reported age. Missing or ambiguous clock/identity evidence is UNAVAILABLE.

Retain the exact admission result and reason, invariant ordering/age predicates, consumer activation/consumption time, current availability check, guidance lease/expiry, and revalidation at actual UI/manual exposure. `publication_completed_utc` stays null unless a real completed publication witness exists. Offline acceptance is not delivery evidence. The detached acquisition path, trusted clock infrastructure and exposure checks remain gates, not accomplished facts.

## 7. Outcomes and review economics

For research record first later quote crossing each preregistered target/stop, prior observation and gap status, horizon end reason, path completeness, arm/exit records, and candidate/contract denominators. Gross cents equal recorded later BID minus immutable original ASK. No fees, liquidity, fills or manual executions may be inferred. If a user actually executes manually, preserve that as a separately consented and independently identified execution record; it must never be synthesized from quote touch.

Round 2 requires the full eligible-origin denominator, including never armed, armed without exit, unqualified entry, unavailable and no-signal contracts. It also requires genuine V8.1 publications and state transitions for any V8.1 claim. Historical clean169 reconciliation separately requires original 49,574-row export SHA256 9c82646867c34b4534e6cf72b498bb760e08d531cf10187757a130e7a6911a3a. The113 reversal baseline requires its actual source export/hash, exact historical report, source code/policy and partition membership; a contemporary service counter is not a replacement.
