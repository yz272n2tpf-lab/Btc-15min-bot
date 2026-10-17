# Short EARLY evaluation preparation

Baseline: `d50d83eda2e433cedc2aeafab8e280c05284afe4`. No deployments or native
capture occur in this work. Existing reader, checkpoint and original evidence
remain. The 600,000-record capacity test is not rerun.

The pinned MAIN `completed_candles` implementation has SHA-256
`f4ff1bbaf1da21a025c5f1e073c651ae430756b6074d26d4481ac9ba98541f2a` in both
native base `4f9ffe51ff9af6adf3f1eb0bd4a77f91dc2caa7c` and this source tree.
It sets index and `source_utc` to original bucket start + 60. New versioned
capture carries original bucket start plus both unchanged native end clocks.
The reader verifies the exact relationship and original HTTP join, storing
the unchanged native row for information associations. Legacy evidence keeps
its old strict schema; no historical rows or timestamps are repaired.

`ReaderLease` refuses a second bounded reader on the host UID before opening
any DB, and on Railway also holds the existing research volume lock. Lock
files are never unlinked. Process death releases locks. All jobs remain serial,
one service replica; no mixed legacy-reader jobs or external SQL inspectors
while a reader runs. The prior concurrent corruption's root cause is unresolved.
Immutable read-only forensic inspection found references to pages beyond EOF,
with the source DB retaining a nonzero rollback journal. It did not repair or
open the failed DB in recovery mode. This is containment, not a root-cause fix
or a filesystem/power-loss qualification.

Capture-only changes retain existing batching and bounded drain, add admitted,
processed and durable charge/item counters, per-kind admission/oversize shapes,
fsync timing and 1 Hz archive telemetry. First failed admission closes capture
immediately; native owners continue and the campaign remains incomplete. No
queue, oversize, freshness or timing limit is relaxed. These diagnostics cannot
make an uncommitted producer queue survive process death.

Prepared profiles are `early_diagnostic` (60 seconds) and `early_preflight`
(1,200 seconds), separate from the unchanged old profiles. Both reserve 2 GiB
on producers. MAIN/V81/information compressed caps are 16/32/16 MiB and
96/320/64 MiB respectively. Role record and decoded caps are also explicit.
The short-profile finalizer invokes the existing bounded reader and avoids the
old whole-run index and 24-hour projection. Profiles are finite preparation,
not production configuration or authorization.

Run the bounded offline regressions with:

```sh
python -B -m unittest research.early_10_12h_20261017.test_preflight
```

Generate conditional duration budgets (no network or mutation):

```sh
python -B -m research.early_10_12h_20261017.plan
```

`baseline_metrics.json` identifies preserved measurements and their receipt
hashes. Rates come from short incomplete bursts. SQL ratios come from explicitly
synthetic retention tests; neither is a sustained healthy native forecast.
The 10/12-hour scenarios include the original 540-second allowance, one startup
sample and a 50% margin. Information traffic, current native-journal growth,
current free space and account billing remain unmeasured gates. Do not resize
from these scenarios. The 48 GiB reader ceiling is unchanged and fails them.

See `SCORING.md` for the prospective EARLY report definition. A complete 10-hour
cohort has 40 full contracts; 12 hours has 48. No minimum BUY count is invented,
and a small sample cannot establish production accuracy. Old checkpoints remain
usable with their exact old code and inputs; cross-code checkpoint migration is
intentionally rejected. Native preflight and evaluation require separate approval.
