# Reproduce offline from the recovered originals

Use this commit's existing Python environment. Extract
`BTC15_Authentic_Diagnostic_Raw_20261017.zip` into a **new** directory; its root
contains `raw/main`, `raw/v81` and `raw/information`. Set `BTC15_AUTHENTIC_ROOT`
to that directory. Never point the output at the historical Railway recording.
These commands have no producer or network dependency.

Run the forensic decoder/accounting assertions once from the repository root:

```bash
python -B -m research.authentic_diagnostic_evidence_20261017.investigate \
  "$BTC15_AUTHENTIC_ROOT/raw" "$BTC15_AUTHENTIC_ROOT/forensics-final"
```

The helper uses the existing record verifier and information-vector codec. It
is not a qualification reader; its output never overrides quarantine. It
refuses an existing output directory. All admitted counts, per-kind admission
charges, old processed charges and immutable record chains are asserted against
the original terminal/seal files.

Prepare two isolated inputs, retaining the existing finisher's file naming and
scope format, then run the existing reader **sequentially**:

```bash
python -B - <<'PY'
import json, os
from pathlib import Path
from ops.live_recording.finish import validate_seals
from ops.live_recording.policy import canonical, file_sha
root=Path(os.environ['BTC15_AUTHENTIC_ROOT'])
seals={}
for role in ('main','v81','information'):
    p=root/'raw'/role/'seal.json'
    seals[role]=dict(seal=json.loads(p.read_bytes()),sha256=file_sha(p))
config=json.loads(Path('research/native_diagnostic_20261017/campaign.approval-draft.json').read_bytes())
validate_seals(config,seals)
for name in ('replay-f1','replay-repeat'):
    work=root/name/'run';work.mkdir(parents=True,exist_ok=False)
    for role,item in seals.items():
        for obj in item['seal']['files']:
            source=root/'raw'/role/obj['path']
            assert source.stat().st_size==obj['size'] and file_sha(source)==obj['sha256']
            if obj['path'].endswith('.gz'):
                stream='information' if role=='information' else 'source'
                dest=work/(stream+'.segments')/(role+'-'+source.name)
                dest.parent.mkdir(exist_ok=True);os.link(source,dest)
    scope=dict(schema='BTC15_CAMPAIGN_SCOPE_V1',run_id=config['run_id'],
               seals=[x['seal'] for x in seals.values()])
    (work/'campaign-scope.json').write_bytes(canonical(scope))
PY
python -B -m ops.live_recording.finish --read-only "$BTC15_AUTHENTIC_ROOT/replay-f1" --profile early_diagnostic
python -B -m ops.live_recording.finish --read-only "$BTC15_AUTHENTIC_ROOT/replay-repeat" --profile early_diagnostic
python -B -m unittest -v research.authentic_diagnostic_evidence_20261017.test_authentic
```

Expected: seven authentic regressions pass; both reader summaries remain
INCOMPLETE, with 27 V81 causal matches, seven information failures, one missing
exact original BRTI association and the original capture-stop limitations.
The five compared ledgers are byte-identical. Exit zero means execution
completed; it does not mean the diagnostic qualified.

The existing 18 parent-fix regressions are
`research.native_diagnostic_fixes_20261017.test_fixes`. The six candle methods
are listed in `test-results.txt`. The corrected selector for the one batch
comparison is
`research.main_closeout_incremental_20261015.test_recorder_burst_batch_research.RecorderBurstTests.test_original_jsonl_hash_chain_unchanged_by_batches`.
Do not run capacity suites or any deployment/capture command for this replay.

`export_once.py` and `export-start-command.txt` are receipts for the completed
research-only export, not instructions to deploy or run it again. All required
bytes are now in the verified ZIP and the untouched historical research volume.
