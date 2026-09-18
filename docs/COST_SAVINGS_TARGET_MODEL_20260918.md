# COST SAVINGS MODEL — TARGET STATES

Railway approximation used for engineering planning:
monthly ~= avg_RAM_GB*10 + avg_vCPU*20 + public_egress_GB*0.05.
This is NOT an invoice.

## Known removed problem
Legacy repeated public scalp export model: ~$100.21/day (~$3,006/30d) if sustained.
13/13 private migration target removes that specific internal-export egress component.

## Current engineering baseline
Producer + adapter V1 + 13 scalp consumers captured around 39.5 GB avg RAM + 1.67 vCPU in a noisy 1h window:
~$428.5/month equivalent before other services.
Main Btc-15min-bot is an additional major service (~4.40 GB RAM + ~0.485 vCPU over 24h).

## Scenario targets (illustrative, must be replaced by measured stabilized 24h)
A. Research-active optimized:
- shared adapter <=0.20 GB
- 13 bounded consumers avg <=0.50 GB each = 6.5 GB
- main bot unchanged 4.4 GB
- lightweight plumbing ~<1 GB aggregate
RAM ~12.1 GB => ~$121/mo RAM plus CPU.
Goal total engineering run-rate: preferably <$160/mo while research remains active.

B. Production-like after research freeze:
- completed research services stopped/frozen
- main bot optimized during plumbing
- shared feeds + dashboard/scoreboards lightweight
Goal should be materially below research-active state; exact target set only after main-bot audit.

## Decision rule
Do not accept a cost target by disabling required evidence collection. First bounded-state; then freeze-and-stop only experiments whose evidence objective is legitimately complete.
