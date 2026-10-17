# Proposed minimal rollout — not executed

Target: a fixed, boundary-aligned 10-hour EARLY cohort; choose 12 hours only
before starting if measured capacity and authorization support it. Evaluation
and production acceptance are separate decisions. No deploy, restart, resize,
production configuration edit, native capture or evaluation is authorized here.

## Preparation before asking for native activation

1. Build exact owner-specific capture overlays against MAIN base
   `4f9ffe51ff9af6adf3f1eb0bd4a77f91dc2caa7c` and V81 base
   `6e04aced0f718b29f8ed805abcc0f76b01ed5096` with the existing allowlisted
   installer. Preserve every protected strategy byte and the native manifests.
   Bind exact new manifest/build/config hashes before seeking deployment
   approval. The prepared research branch is not itself a substitute owner
   deployment bundle. Full pinned-tree inventory hit missing Git objects and
   a proxy failure in this session; it was stopped without repeated retries.
   Bundle preparation/attestation is therefore explicitly incomplete.
2. Refresh read-only free space, native-journal growth, current account usage
   and affordable incremental cost. Keep all historical data and seven existing
   volumes. Preserve the four pending production changes; never apply the whole
   pending environment patch. No new infrastructure is proposed.
3. Confirm the existing research service has one replica, jobs serialized and
   restart NEVER. Test the new global lease on its existing mounted filesystem
   under separately authorized execution. Local process tests passed; the
   platform has not run this new commit. Keep external SQL inspectors and the
   legacy whole-run reader out while the bounded reader holds the lease.

## Approval A: one 60-second diagnostic

Request exact named owner builds/configuration and a unique campaign directory.
Use `early_diagnostic`: MAIN/V81/information compressed caps 16/32/16 MiB;
decoded caps 128/256/128 MiB; record caps 20,000/200,000/50,000. Duration 60 s;
2 GiB operating reserve per producer. MAIN and information share its volume.
Refresh free space; require >=2 GiB + combined role allowances before starting.
No resize is proposed for this diagnostic if those checks pass.

The 32 MiB / 16,384-item queue, 4 MiB conservative observation cap, 1 MiB /
256-envelope batch and existing hook timing gates are unchanged. First loss,
oversize, invalid schema or original journal gap disables capture admission.
The worker drains accepted work; any loss/timeout stays INCOMPLETE, including
late seals. Capture shutdown must leave native owners and strategies running.

Read original oversize kind, conservative charge, raw length/type and field
count. Never store sensitive rejected contents or simply enlarge the limit.
Collect 1 Hz original telemetry, admission rates, durable drain rates, byte/item
deficits, fsync timings, hook timings, phase and compressed/decoded growth.
Exclude any explicitly inconsistent counter snapshot from rate calculations.
Telemetry itself counts toward budgets and must not cause source loss.

Pass only if all applicable roles seal cleanly, clocks/identities agree, zero
losses occur, accepted work is drained, and original freshness/timing/proof
gates remain intact. A 60-second interval is diagnostic, not sustained capacity
or EARLY accuracy evidence. Stop and investigate the first failure; no retry loop.

## Approval B: one 20-minute native preflight

Only after A passes, request `early_preflight`: 1,200 s, compressed caps
96/320/64 MiB; decoded caps 512 MiB / 3 GiB / 256 MiB; record caps
160,000/3,200,000/100,000. Information caps remain provisional until A measures
its traffic. Reserve 2 GiB per producer. Current 20,000 MB MAIN and 5,000 MB V81
allocations are unchanged; last known free space is old, not a current promise.

Cross a real contract boundary. Collect all original inputs and any applicable
BUY/management/outcome records. The absence of a BUY must be reported as such,
not fabricated or considered infrastructure failure by itself. An unavailable
settlement remains pending. Use the existing private transfer/finish path;
these new profiles now invoke the bounded reader without rebuilding the old
whole-run index. Verify exact interrupted/resumed ledgers on the same data.

Measure healthy warmup separately from at least 900 s of steady operation.
Require sustainable drain > arrival and 1.5x burst-deficit margin within the
existing byte/item queue. Quantify SQLite bytes per healthy envelope and per
verified lifecycle, largest rollback journal/temp/export use, checkpoint/recovery
latency, peak RSS and exact original source retention. Include all three roles.
Reader resume tests do not qualify producer crash continuity.

## Approval C: 10 hours, or a preselected 12 hours

Use measured healthy results to replace the conditional estimates, check records
and decoded bytes independently, and prepare a finite duration profile plus exact
storage and spending request. No 10/12-hour capture profile is enabled in this
commit because information rates and reader sizing are still unresolved.

Conditional compressed requirements with one startup sample, 540-second total
allowance and 50% margin:

| Duration | MAIN | V81 | Combined, excluding information |
| --- | ---: | ---: | ---: |
| 10 h | 2.577 GiB | 8.277 GiB | 10.855 GiB |
| 12 h | 3.084 GiB | 9.908 GiB | 12.992 GiB |

Add existing usage, native-journal growth, information and 2 GiB operating
reserve on each producer. Under these scenarios V81's old 2.49 GiB free space
cannot support either run. Rough single-campaign V81 allocations are around
14,000 MB (10 h) or 16,000 MB (12 h), conditional on refreshed existing usage;
do not resize from these old readings. MAIN may fit its existing allocation,
but must include the colocated information role and native growth first.

Synthetic source/quote SQL mixes imply 73.36/87.81 GiB at the burst scenarios;
with 50% margin, 110.04/131.72 GiB. The 48 GiB ceiling and existing 100,000 MB
research volume fail those scenarios. Actual healthy MAIN/V81 lifecycle and
information growth may differ. Do not remove evidence or silently prune exact
dependencies. If measured growth remains excessive, review exact-state storage
compaction and its equivalence proof, or explicitly budget a larger finite store.
Do not spend on a blind resize. Budget rollback/temp/export/source space too;
`plan.py` includes a conservative full-DB rollback contingency, not a measured
journal requirement.

At the checked $0.15/decimal-GB-month volume rate, retaining the margin-sized
MAIN+V81 data for one month is about $1.75/$2.09; the synthetic margin-sized SQL
state alone is $17.72/$21.21. These exclude information, existing storage, native
journals, copies, CPU, RAM, egress and plan credits/subscription. Storage is
metered over retention time. This is not the bill for the run and does not prove
the total account will remain under $20. Source: https://docs.railway.com/pricing/plans

For actual cost budgeting, add RAM-GB-hours * $10/730, vCPU-hours * $20/730,
egress-GB * $0.05 and actual retained GB-days * $0.15/30; 730 h / 30 days are
planning approximations. Existing account headroom must be checked. Evidence
retention is ongoing unless separately authorized otherwise; do not assume
deletion after the test to make the estimate fit.

## Scoring, acceptance and subsequent launch

Follow `SCORING.md` with frozen UTC boundaries and all 40/48 contract outcomes.
If producer interruption loses uncommitted original receipts, preserve the run
as incomplete; no restart/backfill may claim an uninterrupted cohort. Review
EARLY behavior and demonstrated weaknesses. Any strategy change is a later,
separately authorized task with fresh evaluation evidence. Complete production
acceptance before launching the signal-only bot, then reassess after several
days of new forward live data. There is no automatic transition between steps.
