# Main integrity release candidate — 2026-09-23

Scope: SIGNAL ONLY / NO ORDERS. No strategy threshold, weight, contract-timing,
target, settlement, or freshness threshold is changed.

This candidate combines:

- PR30: render-time validation of V8.1 quote/BRTI source provenance;
- PR26: executable-entry accounting that rejects legacy or unverified prices;
- a restart-safe fair-model identity and the historical candle-availability fix.

The fair model is loaded, never fitted, by production startup. The loader checks
the artifact SHA256 before deserialization and recomputes the fitted tree plus
calibration weight hash afterwards:

- artifact SHA256: `2973e4e44d9a0212d3efc443d58956073ba8209cf340fd5d6730c462ab7534c6`
- fitted weights SHA256: `4cdb63db4e2b977592f158147cab650c861c683bf1218556878463120dafeee2`
- fit membership: 331 frozen contracts;
- calibration membership: 133 frozen contracts / 1,862 snapshots;
- historical evaluation membership: 199 already-opened contracts, not a new holdout.

Completed one-minute candles become available only at bucket end. Live partial
BTC inputs retain separate Coinbase source and process observation timestamps.
Missing, future, or older-than-10-second spot provenance fails that cycle closed.

The deployment starts a new strategy/runtime identity. Results from the prior
main revision remain preserved but must not be pooled with this revision for
performance certification. The predeclared frozen common-universe calendar is
unchanged; each row must retain its actual revision and qualification status.

PR26's four exit hypotheses remain predeclared research policies. This release
does not select one or alter V8.1 exit thresholds without prospective corrected
entry evidence.
