# BTC15 Post-Rollover Production Regression Gate V1

Run only after pre-discovery shadow proves repeated exact ticker/open-time matches.

## Must pass before production promotion
- Exact next KXBTC15M ticker staged before official boundary.
- No early activation: staged ticker cannot become active before its official open_time.
- At/after boundary, staged ticker matches Kalshi OPEN contract.
- Contract open/close timestamps preserve exact 15-minute alignment.
- Kalshi target provenance unchanged and target ready for the same contract.
- BRTI transport/value/parity behavior unchanged.
- Websocket order-book subscription uses only the verified active ticker.
- Timestamped YES and NO books become usable with normal provenance.
- EARLY protected Tier-1 thresholds unchanged.
- FINAL protected qualification unchanged.
- SCALP detector/qualification logic unchanged.
- Dashboard/source publication semantics unchanged except earlier valid rollover readiness.
- Fail closed on ticker mismatch, missing metadata, stale/future source, or unusable book.
- signal_only=true and orders=false throughout.
- No order-placement code introduced.

## Promotion evidence
Compare shadow vs current production over multiple live boundaries:
staged_at, seconds_before_open, boundary verification, production selected_at,
subscription, first market data, both sides ready, first valid source.

No production edit is authorized by this document.
