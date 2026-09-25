# Two-clock field authority contract

There are exactly two classifications: `INFORMATIONAL_READ_ONLY` and `AUTHORITATIVE_ACTION_STATE`. Authority describes which stream can write a field. It does not convert a shadow observation into connected position advice, and never permits orders.

## New public information API

`/information` and `/information/frame/<exact hash>` use a closed field set from `btc15_information_v1.FIELD_CLASSES`. Every field below is **INFORMATIONAL_READ_ONLY**, including metadata and WAIT values. Unknown output fields are not emitted. The exact machine map is served at `/information/schema`. This route's `schema`, `fields`, `signal_only`, `orders`, and every map value are also INFORMATIONAL_READ_ONLY. Unknown routes expose only an informational error.

| Exposed fields | Meaning / constraint |
|---|---|
| `schema`, `authority`, `status`, `reason`, `signal_only`, `orders` | Information schema; AVAILABLE or WAIT. `authority=INFORMATIONAL_READ_ONLY`, `signal_only=true`, `orders=false`. AVAILABLE means source-qualified information, never entry eligibility. |
| `frame_id`, `anchor_id`, `native_epoch`, `native_decision_ts` | Immutable frame identity and exact committed native input basis. Native timestamp is historical lineage; it is never advanced by a fast refresh. |
| `evaluated_ts`, `published_ts`, `checked_ts` | New informational cutoff, completed publication time, and current display qualification time. None replaces a source timestamp or authoritative decision timestamp. Repeated queries change only current checking metadata/age/time-left. |
| `expires_at`, `display_until` | Minimum unchanged source/contract deadline; additionally bounded by the one-second health lease for rendering. Clients must recheck on every render/timer and fail closed when disconnected. A new check cannot move `expires_at`. |
| `ticker`, `target` | Native-authorized contract and fixed official target; the information layer cannot roll over independently or change a target for the same native owner/contract. |
| `btc_price`, `btc_source_ts`, `btc_received_ts` | Last native-observed Coinbase spot, with original clocks. This minimum design does not add faster Coinbase polling. Price can be up to the unchanged 10-second BTC source limit; UI must show its timestamp. |
| `brti_value`, `brti_source_ts`, `brti_received_ts`, `brti_age_seconds`, `brti_side` | Exact existing owner's causal BRTI observation. Age is checked at capture, after inference and at display; maximum remains 5.0 seconds. Side is descriptive relative to target. |
| `quote_source_ts`, `quote_received_ts`, `up_bid`, `up_ask`, `down_bid`, `down_ask` | Replayed immutable quote proof. Source time is exchange time; receipt is conservative snapshot-availability time. Existing six-second quote limit is preserved. No latest-proof substitution. |
| `probability_up`, `probability_down`, `model_flip_probability` | Frozen fitted probability arithmetic on committed BTC history at the informational cutoff. The model's flip is final-outcome relative to current target side; it is not an entry-specific reversal probability, trade-exit rule, confidence guarantee or new FINAL CALL. |
| `probability_up_change_since_native` | Current descriptive probability minus the explicitly timestamped native baseline. The baseline is historical context; it is not carried forward as a current assessment. |
| `preferred_side`, `brti_agrees`, `btc_gap`, `brti_gap` | Descriptive direction/agreement/gaps only. No EARLY/SCALP/FINAL readiness, HOLD, CAUTION, PROTECT, EXIT or FLIP action. |
| `range5`, `dist_over_range5`, `seconds_left` | Frozen descriptive feature/window context, calculated from immutable committed inputs. No accumulated fast history, persistence hits or new partial-candle state. |
| `artifact_sha256`, `weights_sha256` | Pinned model identities; no fitting or parameter selection. |

WAIT redacts **all** source-dependent fields, identities, model assessment and quotes to null. Only schema/classification/status/reason/safety and check time remain. There is no last-good assessment fallback.

The optional JavaScript adapter captures a response once with its actual monotonic HTTP request-start and receipt times. Every render conservatively adds the entire request elapsed time to the server check clock; local device UTC skew cannot revive stale information. Old-page serialized tokens, slow responses and clock regression fail closed. Its timing token and payload are INFORMATIONAL_READ_ONLY. It returns only `information.authority/status/label/assessment`, all INFORMATIONAL_READ_ONLY. Its assessment is an explicit subset of the table. `twoClockView().authoritative` retains the original native object unchanged, classified AUTHORITATIVE_ACTION_STATE at that namespace boundary. It does not merge information into native cards or renew the native clock. The adapter is not installed in the production dashboard.

## Existing stream and state domains

| Existing fields/state | Classification and owner |
|---|---|
| Native decision timestamp/ID; `early.ready/status`, `scalp.ready/status`, `final.ready/recorded_final_call/recorded_status`; all entry eligibility/gate outputs | **AUTHORITATIVE_ACTION_STATE**: existing main/dashboard semantics on original rows only. These gates still do not supply a missing connected position ledger. |
| Entry ID/origin/time/price, position side/status, target/stop/protection advice, HOLD/CAUTION/PROTECT/EXIT/FLIP, cooldown/repeat arbitration | **AUTHORITATIVE_ACTION_STATE**: original owner or an explicitly future approved lifecycle owner. No corresponding fast information fields exist. Undefined or NOT_LINKED remains so. |
| Histories, sampled BTC ticks, partial-candle inputs, rolling-feature caches; early/unified persistence; general/true-scalp/profit pending state; iterations, timestamps, saved state and publication logs | **AUTHORITATIVE_ACTION_STATE** for write access: sole original writer as inventoried in V2. Original shadow state remains shadow; this classification reserves its cadence and does not promote it. Information receives only serialized whitelisted inputs and derives disposable features. |
| Quote book/sequence/rebase state, delivery samples/status/epoch, contract staging, BRTI closeouts, diagnostic throttles | **AUTHORITATIVE_ACTION_STATE** for write access: existing source/runtime owner. Reads cannot ingest samples, call consume, switch tickers or overwrite proof files. Current copied source health/provenance is informational. |
| Existing fair probabilities, raw source/market context, shadow telemetry and hypothetical target/stop numbers when displayed as observations | **INFORMATIONAL_READ_ONLY** as observations. Native gates/lifecycle consuming their original-clock versions remain authoritative. Equal numeric names across domains do not authorize cross-wiring. |
| `scalp.position_status='NOT_LINKED'`; actual `target_bid`/`stop_bid=None` | **AUTHORITATIVE_ACTION_STATE** representing the exact current missing connection; retained unchanged. Hypothetical targets/stops remain INFORMATIONAL_READ_ONLY. |
| `position_protection.*` telemetry; `shadow_only=True`; `safety.shadow_protection_used_as_action=False`; Rescue/parity shadow display | **INFORMATIONAL_READ_ONLY** observations and safety metadata. No actionable authority is conferred. Their producing shadow collectors retain their own original-clock mutable state. |
| V8.1 `active`, native signal origin/provenance, `last_signal_event`, confirmations/repeats, native lifecycle status/targets | **AUTHORITATIVE_ACTION_STATE** within the existing separate V8.1 domain. Does not own EARLY/FINAL. Its current raw source and diagnostics are INFORMATIONAL_READ_ONLY. No V8.1 field is written or recalculated by this candidate. |
| Browser timers, HTTP publication/check times, immutable-frame retention and information dedup state | **INFORMATIONAL_READ_ONLY** infrastructure state. They cannot renew a native decision, create an entry, or make stale information AVAILABLE. |

The internal loopback input route carries only the immutable anchor, original candle/tick/receipt clocks, current copied BRTI/quote proof and content identities. All exposed copies and health metadata are INFORMATIONAL_READ_ONLY. They never grant the reader a reference capable of writing the original owner. The original objects remain in the authoritative write domain.
