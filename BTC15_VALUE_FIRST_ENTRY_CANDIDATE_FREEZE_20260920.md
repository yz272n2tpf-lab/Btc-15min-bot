# BTC15 Value-First Entry Candidate Freeze — 2026-09-20

RESEARCH / DEVELOPMENT FREEZE ONLY. SIGNAL ONLY. NO ORDERS.

## Detector preserved
The generalized movement detector remains unchanged. Kalshi price does not qualify or reject the movement setup.

## Frozen development candidate
After a movement setup qualifies:
- if the executable side ASK is <= 50c, entry guidance may be immediate;
- if ASK is > 50c, keep the move visible as WATCH / WAIT FOR VALUE;
- for up to 30 seconds after the movement setup, the first executable ASK <= 50c is the candidate entry;
- if no <=50c ASK occurs within 30 seconds, no actionable entry is issued for this candidate;
- actual ASK is entry cost; future executable BID scores outcome;
- no entry-price bucket changes the underlying movement detector.

## Evidence snapshot
V2 source SHA: 8dbd61e1e04057b8d123760209c108ccf14d58fd342fbcbe6a82907eda35927a
V2 code SHA: 7f901c87774dd418db79a29f513b05245488a6ba0cedd6e7a8572ac9865ce55f
Full contracts: 352
Serial opportunities: 563

V1_LE50_30S:
- 321 entries / 236 contracts
- average entry ASK 32.013c; median 34c
- 56.386% of entries <=35c; 100% <=50c
- +5c 82.866%; +10c 66.355%; +20c 42.056%
- protected-exit observed 63.240%

Rejected as development alternatives:
- 60-second extension added only 12 entries; avg entry 45.25c, +10c 16.67%, +20c 8.33%, protected exits 0.
- V2_PRICE_DISCIPLINED added 4 entries beyond the 30s lane; avg entry 49.25c, +10c 25%, +20c 0%, protected exits 0.
- V2_BALANCED added 95 entries beyond PRICE_DISCIPLINED; avg entry 68.17c, +10c 64.21%, +20c 30.53%, protected-exit rate 46.32%, protected-exit one-lot taker/taker average net -1.98c.

## Entry-quality studies that were NOT selected
- No BRTI/acceleration hard threshold passed development retention gates.
- 1–4 second micro-confirmation variants discarded too many original +10c winners and were not selected.
- Prior rejected btc30 tightening, normalized-momentum gates, and strict 15s BRTI/BTC parity remain rejected.

## Next
Score protection/exit variants only against this frozen development entry behavior. Do not alter the detector or entry candidate while protection is studied.
