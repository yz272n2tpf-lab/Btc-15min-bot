# Production explanation stability — October 8 Eastern / October 9 UTC

Scope: existing live cockpit only. MAIN remains
`57f468063f31ec005f413e5032d147603c2e70c8`. No signal engine, source owner,
adapter validation, model, threshold, native evaluation timing, source freshness,
protected ladder, service configuration, volume, or order behavior changes.

## Observed cause

Real production browser, current contract `KXBTC15M-26OCT082015-15`:
at 00:12:25.953 UTC a MAIN lease gap replaced FINAL's
“FINAL probability is below 90%.” and EARLY's protected 45-cent PASS reason
with generic unavailable text. At 00:12:26.145 UTC a fresh publication restored
the same two reasons. The last-qualified MAIN publication advanced from
00:12:23.256 to 00:12:25.660. This was a delivery-classification transition,
not a different trading decision. Action authority correctly expired.

The renderer also wrote adapter placeholders followed by resolved descriptions
every 100 ms. SCALP side descriptions, BRTI health and market context had multiple
formatters. BRTI health was written by the adapter, market and information paths.
The model explanation included transient delivery classification in its text.

SCALP's real changes were different: newer publications removed a price-pullback
warning at 00:12:23.045, changed CAUTION to PROTECT at 00:12:29.079, and restored
the warning at 00:12:32.176. These legitimate changes must remain immediate.

## Correction

`cockpit_candidate/cockpit.js` assigns live explanatory/descriptive fields to
one formatter, skips adapter placeholder writes for those fields, and avoids
replacing the identity Details table twice per resolution. Exact unchanged
values do not mutate their text nodes.

When current authority expires, actions, prices and active rungs still come
exclusively from the current adapter projection. Only validated same-contract
explanations can remain from the source owner's existing retained publication.
The separate freshness label immediately says no current action authority and
LAST QUALIFIED (historical), with the delivery reason. SCALP side descriptions
also carry explicit historical labels. Recovery never changes a deadline.
New native reasons and binding rejections display immediately. Rollover clears
old-contract explanations; there is no presentation debounce or new cache.

BRTI health has one formatter for the existing original-timestamp sources,
retaining the five-second check. Model content is separated from its adjacent
current/historical classification. The layout and source subscriptions remain.

`test_explanation_stability.cjs` exercises the actual renderer and native adapter:
100 unchanged renders produce zero explanation writes; expiry removes all action
authority but retains labeled explanation history; recovery, native reasons,
invalid bindings and rollover behave correctly. All 50 existing protected
scenarios retain native actions, reasons, prices and rungs. Asynchronous market
and information callbacks cannot alternate competing wording.

Existing checks: descriptive-renderer startup/expiry/rollover; eight focused
adapter checks; source-owner parity: 13 scenarios, 85 checkpoints, 572 rendered
comparisons. Runtime manifest updated only for cockpit.js.

## Rollback

Existing cockpit service `b584a1cf-a951-4b54-9127-4826cedc3ccb`, project
`baea4e22-d004-4434-b2c5-81a7fbc05086`, production environment
`61775c5d-c583-4dfc-af41-f25578856fd9`.

Re-pin the cockpit to `24a746dbc7aa8a0e17c821d5952f5751bb64e764` on
`fix/btc15-live-cockpit-source-visibility-20261008`, keeping root
`/cockpit_candidate` and current commands. Previous successful deployment:
`2e3003a1-c9f1-4d10-a188-10689cf0bfb7`. Do not apply unrelated staged changes.
No MAIN, SCALP, BRTI or storage rollback is needed for this presentation repair.

## Live follow-up

First release `1e0dd2ceeb0d71da062cd81e776d9d605bf6fb7a`, deployment
`33389911-1532-4b58-b866-74ab92a44cf8`, confirmed stable trading reasons
through an actual QUOTE_SOURCE_UNAVAILABLE interval and recovery. Real FINAL
and EARLY conditions changed immediately with new publications. The mobile
browser then exposed a remaining vertical jump: multi-line refresh labels and
inserted historical-price paragraphs moved unchanged explanations.

The follow-up keeps classification in a reserved two-line status area, normalizes
the equivalent pending/expired delivery wording, and keeps historical prices in
Details. It reserves space for the existing source header and EARLY context.
This small `styles.css` adjustment accompanies the data-ownership correction;
no warning, reason, or authority deadline is delayed. Final production and
real-browser results will be appended after release.

Live geometry measurements also identified the empty phase guard collapsing
the header, source/quote labels changing line counts, and historical prefixes
wrapping the SCALP side headings. The final adjustment reserves those status
rows and gives each SCALP side its own adjacent freshness label in `index.html`.
The UP/DOWN explanation itself remains unchanged through expiry. All historical
labels remain visible immediately; no text is clipped and no update is delayed.
