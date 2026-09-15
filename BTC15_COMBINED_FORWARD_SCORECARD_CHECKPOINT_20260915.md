# BTC15 Combined Forward Scorecard Checkpoint — 2026-09-15

**Mode:** READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

## Deployment
- Railway service: `combined-forward-scorecard-v1`
- Service ID: `e9399baa-25a8-4801-a374-ae6c5401060d`
- Correct deployment ID: `2c5c362d-1469-4b5b-8d3c-b2c4e0b46084`
- Source branch: `scalp-move-shadow-v1-20260912`
- Source commit: `b754e7232ff1f4a0da8b79da65616cf26456248d`
- Status: **SUCCESS**

A separate initial Railway bootstrap snapshot incorrectly came from `main` and failed closed because the research-only test files did not exist there. It collected no evidence and is not part of this test.

## Startup safety gate
Test-first command ran:
- `test_btc15_combined_empirical_scorecard_v2.py`
- `test_BTC15_COMBINED_FORWARD_SCORECARD_V1.py`

Result: **16 tests PASS**.

Covered invariants include:
- multiple serial SCALPs in one contract count as multiple opportunities but one SCALP-covered contract;
- EARLY + multiple SCALPs + FINAL still count as one UNION-actionable contract;
- expensive but correct FINAL remains correct while failing the <=50c entry metric;
- WATCH is non-actionable;
- ENDED_UNARMED remains a non-actionable lifecycle end;
- contract mismatch fails closed;
- order-capable payload fails closed;
- duplicate contract records cannot double-count union coverage;
- no production behavior or module threshold change;
- no numeric flip-risk invention;
- no orders.

## Fresh-forward integrity
Frozen cutoff: `2026-09-15T18:00:00Z`.

Runtime started before the cutoff. First real runtime summary after startup:
- observed contracts: 0
- settled contracts: 0
- EARLY calls: 0
- SCALP contracts/opportunities: 0 / 0
- FINAL calls: 0
- UNION: 0 / 0
- sample ready: False

The `A -> B` rollover / EARLY / FINAL / SCALP lines that appear before unittest `OK` are deterministic test fixtures, not live market evidence.

The live observer excludes the contract already in progress at process startup and arms only on the first real contract rollover at or after the frozen cutoff. Therefore the first counted contract will be observed from its beginning.

## Frozen review gate
- >=30 fully observed common-universe contracts
- >=25 officially settled contracts

At that gate report separately:
- protected EARLY accuracy / coverage / ask / timing;
- serial V5 SCALP contract coverage, opportunity count, +5/+10/+15/+20, entry economics and management;
- protected FINAL accuracy / coverage / locked-side ask / timing;
- path-combination counts;
- UNION actionable coverage with each contract counted once.

## Anti-drift
This scorecard is measurement/integration validation only. It cannot retune or auto-promote EARLY, SCALP, or FINAL. Production remains untouched. Manual execution only. No orders.
