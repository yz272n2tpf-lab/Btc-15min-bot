# Model integrity blockers identified during completion

Production weights and thresholds are unchanged. These findings block strategy certification, even if infrastructure rollovers pass.

September23 continuation: current main c482468 started at12:59 with **56 calibration contracts /784 snapshots**, independently retrieved from that deployment's startup log. The57/798 reproduction below belongs to the earlier12:26 runtime and must not identify the later model. The exact support-expiry reproduction finds the existing20-contract calibration floor fails immediately after **September25 12:45:00 UTC**. Actual live weight bytes are not currently exported; any main restart invalidates the registered runtime identity.

Draft PR25's completed-candle/frozen-support candidate remains offline. Hosted run35865718174 ran11 tests successfully with production pins numpy2.5.2/pandas3.0.5/sklearn1.9.0. Both independent331-contract fits produced weight SHA256 `95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6`; prediction difference2.7755575615628914e-16. This proves deterministic fitting in that environment, not forward accuracy or readiness for promotion. Live clean input capture now retains BTC source/receipt and BRTI source/epoch; full paired model integration/evaluation remains outstanding.

## Restart changes the supposedly frozen fitting universe

The fair engine loads fixed August15–22 labels and a fixed BTC cache ending September2. At startup it discards BTC history older than wall-clock now minus35 days, then recomputes its50% fitting /20% calibration split over the surviving contracts. Thus a restart changes the fitted model without a code or threshold change. Eventually it removes all labeled support.

`audit_training_support.py` executes only the existing pure feature functions against the committed inputs, without credentials/network/fitting. Its result reproduces the deployed September23 calibration log exactly:57 contracts /798 snapshots.

| Restart at12:26:30 UTC | Eligible contracts | Fitting contracts | Calibration contracts | Existing >=20 calibration gate |
|---|---:|---:|---:|---|
| September2 |663|331|133|PASS|
| September22 |379|189|76|PASS|
| September23 |283|141|57|PASS|
| September24 |196|98|39|PASS|
| September25 |100|50|20|PASS, at the minimum|
| September26 |4|2|0|FAIL|
| September27 |0|0|0|FAIL|

Recent live bars cannot repair missing August history. A running process may retain a trained model while the same revision fails after a later cold start. This is a concrete old-container-state dependency. No calibration minimum was lowered.

## Historical candle availability is one minute late relative to its index

Coinbase documents its candle timestamp as the bucket start; its close/high/low describe the bucket's trades. The loader uses that timestamp unchanged. The historical fair builder admits a complete row at index<=decision cutoff and checks only that index. At a minute boundary it therefore uses the next minute's eventual close and high/low.

Reference: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles (Response Items, retrieved September23,2026).

`audit_candle_availability.py` mutates only the12:35 bucket's eventual close/high at a12:35 decision cutoff. Eighteen feature values change and the existing future-data guard does not raise. The completed bucket is not available until12:36. This is a reproduced historical feature defect; it does not imply production has access to future prices.

## Offline candidate exploration, never promoted

`fair_candidate_replay.py` freezes the original663 contract identities and input hashes, preserves the existing900-tree RF parameters and sigmoid settings, and compares three representations. The candidate indexes completed historical candles by availability time (bucket end), without discarding old fitting support by current date. This is not yet a live partial-bar integration patch.

The shared, previously inspected historical evaluation contains85 contracts /1,190 minute snapshots. Contract-averaged Brier score (lower is better): original representation0.172384; current shrinking-history representation0.159641; completed-candle candidate0.188563. The candidate's full original199-contract historical evaluation is0.173145. Different timing representations change the information available to a prediction; these numbers are not a reason to retain look-ahead or select a favorable split.

No accuracy/coverage claim, threshold search or production promotion follows from this replay. Historical evaluation has already been opened. It lacks contemporaneous executable quotes and call-time BRTI, so it cannot establish qualified EARLY/FINAL/SCALP performance. Correct live partial-bar handling, a fixed model/data identity, leakage regressions and a genuinely new forward cohort remain required together.

## Next coordinated correction boundary

Keep the current infrastructure candidate stable for acceptance. Prepare a separate model-integrity candidate with explicit completed-versus-partial candle availability, immutable fitting/calibration membership and hashes, equivalent live price/clock/target semantics, and restart reproducibility. Test mutation of every unavailable input, missing history, future timestamps and exact candle boundaries. Do not restore old scores as certification, silently retrain production, lower gates, or remove any ladder. Before promotion, report effects on all three ladders on separated evidence.
