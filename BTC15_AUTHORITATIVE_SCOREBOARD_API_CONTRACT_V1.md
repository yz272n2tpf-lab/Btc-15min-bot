# BTC15 Authoritative Scoreboard API Contract V1

**Presentation / integration only · read only · signal only · manual execution · no orders**

This contract defines how `BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V1` may be consumed
by future dashboard/UI work. It does not change any signal, lifecycle, threshold,
or production behavior.

## Endpoints

- `/health` — service self-health only. Upstream collector failure must not cause a
  restart loop.
- `/scoreboard` (alias `/state`) — structured current snapshot.
- `/scoreboard.txt` — human-readable one-command-style report.

The service has no write endpoint. POST/PUT/PATCH/DELETE are rejected.

## Source policy

All collector reads must use Railway private networking (`*.railway.internal`).
The scoreboard must not require a collector to be publicly exposed.

Each source must match its exact expected version. A wrong version, HTTP failure,
malformed payload, unsafe flag, or timeout makes that source `NOT CONNECTED` for
that request. No stale source snapshot is reused across requests.

## Allowed user-facing categories

### FINAL
May show:
- officially settled directional accuracy;
- FINAL-only coverage;
- average/median minutes left;
- average/median locked-side Kalshi ask;
- <=50c count/rate;
- sample size / readiness.

Must not imply a high directional score means an attractive entry price.

### EARLY
May show:
- EARLY-only coverage;
- entry ask;
- ideal 25-35c count/rate;
- <=50c count/rate;
- timing, fair, edge;
- sample size / readiness.

Settlement same-side rate must be labeled secondary context, never FINAL accuracy.

### SCALP
May show frozen/reviewed movement metrics such as +10c hit rate and protected-exit
statistics. Every such value must be labeled a price-movement/management metric,
not FINAL outcome accuracy.

### EARLY excursion utility
May show:
- completed opportunities;
- entry price/timing;
- MFE/MAE using live same-side BID minus protected EARLY ask;
- descriptive +5/+10/+15/+20c hit rates and time-to-hit;
- protected FINAL-after-EARLY agreement as downstream context.

These checkpoints are measurements only and cannot silently become qualification
thresholds.

### EARLY -> FINAL handoff
Only an authoritative common-universe handoff sample may show:
- any-anchor/union coverage;
- dual-anchor coverage;
- handoff count;
- EARLY/FINAL side agreement;
- average/median handoff time gap.

Separate EARLY and FINAL collector coverages must never be added together.

### Flip Risk
Until future validation and separate manual display approval:
- numeric value = hidden;
- display status = `HIDDEN_UNTIL_VALIDATED`.

No UI may substitute historical V1 or a current raw/calibrated research probability
for an approved user-facing Flip Risk percentage.

## Overall system section

Allowed:
- per-module scores with denominators;
- common-universe union coverage only when that source is sample-ready;
- readiness / collecting state.

Forbidden:
- one blended `system accuracy` percentage;
- summing coverages from different universes;
- calling SCALP movement rate outcome accuracy;
- displaying stale numbers when a source is unavailable.

## Safety invariants

A source is rejected if it explicitly reports any of:
- `orders=true`;
- `manual_execution_only=false`;
- `production_behavior_changed=true`.

The scoreboard itself always reports:
- `orders=false`;
- `manual_execution_only=true`;
- `production_behavior_changed=false`.

## UI integration rule

Do not replace V12 or promote V13 because this API exists. Dashboard integration
requires a separate presentation-only shadow build and visual acceptance on both
iPhone and iPad. The scoreboard service is data/reporting infrastructure only.
