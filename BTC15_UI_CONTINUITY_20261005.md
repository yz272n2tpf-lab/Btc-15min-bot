# Narrow dashboard continuity repair — review before deployment

Production baseline: MAIN b2209569e8c69ffbf79cb2b219276c95b160f2dc;
V8.1 e7b7ffe6109fbdc064770fba34956f59d94be872 remains unchanged.
SIGNAL ONLY. MANUAL EXECUTION ONLY. NO ORDERS.

The dashboard must show current authorized guidance, PASS with the native gate
reason, or WAIT with the current interruption reason. Informational values may
remain only with explicit LAST QUALIFIED / REFRESHING labels. Retention must
never authorize an action or event, renew a lease, change native clocks/cadence,
or alter strategy/model thresholds, gates, persistence or lifecycle state.

Runtime changes are limited to the ladder display, lower information display,
and dashboard assembly text/plumbing. Existing API UNAVAILABLE statuses remain
fail-closed; presentation shows WAIT. SCALP diagnostics are read from the existing
V8.1 payload. Numeric/model/quote history is used only by the renderer. No BRTI
owner, strategy, native evaluation, lifecycle, record, or transport changes.
The release manifest pins these exact presentation bytes, including the lower
information panel, without changing protected file hashes.

Targeted offline qualification passed:
- 62 full-dashboard checks at 390px and 820px, with revalidation disagreement,
  BRTI expiry, identity/clock rejection, noncausal source rejection, timestamped
  quote loss, official-market interruption, indicator and lower-feed loss,
  recovery, rollover, and replayed expired payloads.
- Zero visible UNAVAILABLE/NOT CONNECTED text, blank checked live fields,
  horizontal page overflow, or stale action guidance in those checks.
- Exact SCALP PASS reasons: price outside 30–45¢, base not ready, evidence below
  CORE/SURGE. Temporary timestamped-quote loss displays WAIT and its reason.
- 15 native observations compared byte-for-byte with the exact production
  baseline tree, including EARLY BUY/HOLD/PROTECT and SCALP signal/exit records.
- Both strategy/model freezes PASS. Two focused native lease/mutation tests PASS.
- Action acceptance, polling, deadline and invalidation functions byte-identical.
  Assembled HTML structure/attributes and all CSS byte-identical; text and
  presentation JavaScript are the authorized differences.

Evidence: qualification/ui_continuity_20261005/results.json. Synthetic offline
fault injection is not a new physical-device acceptance claim. Production was
not deployed or restarted. Publish on a new unattached candidate branch; stage
only MAIN branch, exact commit pin and matching reviewed start command. Review
the staged non-destructive diff and stop for explicit deployment approval.
