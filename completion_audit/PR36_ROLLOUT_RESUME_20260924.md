# Resume after approved PR36 rollout — 2026-09-24

The controlled PR36 rollout is complete; **initial live data-path acceptance PASS, prospective performance acceptance PENDING**. Do not resume obsolete production commit/deployment assumptions in earlier checkpoints. Do not redeploy or repeat the completed release/CI work.

Read the frozen [rollout checkpoint](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/dd47cb42a26f66c34feb4043e535a3f5abe6fc16/completion_audit/PR36_ROLLOUT_CHECKPOINT_20260924.md), [boundary manifest](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/dd47cb42a26f66c34feb4043e535a3f5abe6fc16/completion_audit/PR36_PROSPECTIVE_BOUNDARY_20260924.json), and [live evidence](https://github.com/yz272n2tpf-lab/Btc-15min-bot/blob/dd47cb42a26f66c34feb4043e535a3f5abe6fc16/completion_audit/PR36_INITIAL_LIVE_ACCEPTANCE_20260924.json).

Current production: commit3e552065e34a0a402bc3ca4598b57dff1f1c6e77 / deploymentf82466d0-70ab-4779-a0fd-58832ad31513. Exact tree586f8cfd635d6ed817c63202cdec0b8bcc454e0c matches approved e02f737, hosted238 tests and44 focused checks. Cold start/data archive/model hashes/read-only HTTP/causal BRTI/exact ticker/target/clock/quotes/parity/rollover/fair-value recovery checked live.

Core loop began19:54:18.990766070UTC.19:45 is mixed/restart;20:00 is warmup/infrastructure-only. **First full corrected prospective slot20:15UTC** (at least six minutes after core-loop startup). Fixed validation end21:15UTC unchanged; post17:00 tuning prohibited. Do not count repaired replay or earlier runtime contracts as corrected prospective successes. Four full corrected contracts and longer eligibility/lifecycle/performance evidence remain to accrue. Untouched holdout remains unopened until its fixed end.

No strategy weights/thresholds/freshness changes. Frozen fair weights95fc4e893c9032f29b9732d03c4a2e0cd62755ba93b36106a1d0c8c094520ba6. Any restart/change closes this runtime identity. Shared owner, V8.1 and clean collector deployments unchanged. Collector still clean-source-v2-1s-20260923. Preserve old five-second run separately.

72/72 reviewed decision records qualified BRTI (1.116–3.353s),63 input frames passed range hashes and causal timestamps. These selected decision samples are not continuous availability or full-universe coverage: a71.05251s quote-WAIT/rollover input gap remains recorded.22 parity PASS/6 safe WAIT. Fair output resumed in the new contract at+10.217s; staged handoff+4.960s, parity+22.671s. No trading-performance improvement claimed.

Read-only monitoring should use the new identities and existing separate collector export checkpoint. Next feature-journal byte offset4446952, identity7b9f685f1a3bedfb3afed0dfdb7163806e42dc9ace3ac035ce08870713da0996. Retain exact range hashes; main feature export is NDJSON, clean common export uses gzip CRC. Do not refit/tune or pool revisions.

Rollback preserved: commit1730ceff180394fbd2ebae7a5fddc4acd1e76194 / deployment454f53ad-b269-4133-b0f5-60098978db71 / branch rollback/btc15-before-pr36-20260924. No rollback required so far. Roll back on a verified candidate acceptance failure, do not improvise changes.

SIGNAL ONLY / NO ORDERS.
