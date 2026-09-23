# V8.1 quote-source correction — 2026-09-23

Candidate only. SIGNAL ONLY / NO ORDERS. Base b3951fb3959e6e8b1e7376edc948f53f033a794e.

At 21:22:43.719675 UTC KXBTC15M-26SEP231730-30 published DOWN CORE at 40c. The independent timestamped book showed 57c ask / 56c bid at 21:22:43.511335 and 21:22:44.484548; main independently showed the same prices from its 21:22:42.679139 frame. V8.1's market-list REST response was being used as an untimestamped price source. Fresh publication alone did not establish quote freshness. The old event remains evidence, not a certified executable 40c entry.

## Coordinated change

- Reuse the exact production Book/Evidence/Provider implementation from c482468. Source files btc15_kalshi_quote_provenance_v1.py, btc15_data_paths_v1.py and btc15_rollover_diag_v1.py are copied without strategy changes. The V8.1 subclass atomically returns quote identity/timestamps without per-poll disk writes. Existing branch authentication helper remains unchanged.
- REST remains official contract/target discovery only. A contiguous timestamped WebSocket book supplies both side prices. No REST price fallback, receipt-time timestamp substitution or cross-ticker carryover.
- Read only the existing shared BRTI owner. Revalidate its actual source timestamp after network reads and at signal publication. No additional authenticated upstream BRTI requests or retries.
- Publish immutable entry provenance and current input provenance separately. Missing/invalid sources publish WAIT and clear incomplete confirmation counts. Existing active lifecycle identity survives a recoverable data gap; no fabricated exit or new entry. HTTP reads cannot refresh source clocks.
- Add the matching main consumer guard separately; its 3.5s publication check also validates current quote/BRTI source ages at render time. Keep producer and consumer order explicit.
- Correct PR26 accounting separately: preserve every published event, reject legacy unproven entries, and check the first observed ask after receipt before hypothetical lifecycle scoring. Never search for a later cheaper quote.

The 30–45c band, CORE/SURGE floors, two qualifying observations in four seconds, 20s repeat interval, 180s horizon and +5/+10/+20c diagnostics are unchanged. BRTI remains <=5s; quotes retain the established production 6s bound; publication remains <=3.5s. No ladder/model threshold, weight, target, settlement, or main staged-rollover change.

## Validation and release boundary

Local producer regressions: 22/22 PASS, including the captured 40c/57c incident, both sides, missing/future/stale data, exact official clock/target, gap/reconnect/rollover, actual WAIT loop, immutable entry updates and the existing single-owner regression. Main consumer candidate: 197/197 PASS. Exit/accounting candidate: 14/14 PASS. Hosted results and live acceptance must be recorded separately; these tests do not certify candidate live behavior.

No production deployment in this change. Preserve current deployment rollback points. Before a coordinated rollout, prove the source producer independently, freeze a new V8.1 runtime/policy identity, and retain old common-cohort membership as its original revision. Do not pool changed signals into the original cohort. Main restart changes its current unexported model weights and has a known moving calibration floor; do not restart it merely for this UI guard. PR25's model is still research and requires native integration before a main restart can be certified.
