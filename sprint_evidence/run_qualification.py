"""Isolated, synthetic qualification and genuine host measurements. No market I/O."""
from pathlib import Path
import argparse, base64, hashlib, importlib.metadata, json, os, platform, re
import subprocess, sys, time

ROOT = Path(__file__).resolve().parents[1]
FROZEN_MODULES = [
    'round2_evidence.test_round2',
    'test_btc15_external_evidence_admission_v1',
    'test_btc15_lifecycle_isolation_v1',
    'test_btc15_lifecycle_isolation_native_v1',
    'test_btc15_directional_signal_authority_v1',
    'test_btc15_directional_signal_noninterference_v1',
    'test_directional_position_manager_v1',
    'test_btc15_decision_clock_v1',
]

def restore_test_objects():
    """Restore only exact preserved objects; never create or move a Git ref."""
    objects = json.loads((ROOT/'sprint_evidence/test_git_objects.json').read_text())
    for oid, value in objects.items():
        raw = base64.b64decode(value['base64'], validate=True)
        kind = value['type']
        digest = hashlib.sha1(kind.encode()+b' '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if digest != oid:
            raise ValueError('FROZEN_TEST_OBJECT_HASH')
        actual = subprocess.check_output(['git','hash-object','-w','-t',kind,'--stdin'], input=raw, cwd=ROOT).decode().strip()
        if actual != oid:
            raise ValueError('FROZEN_TEST_OBJECT_IMPORT')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    args = p.parse_args()
    out = Path(args.output).resolve(); out.mkdir(parents=True, exist_ok=True)
    restore_test_objects()
    sources = json.loads((ROOT/'sprint_evidence/qualification_sources.json').read_text())
    mismatch = [name for name, digest in sources.items()
                if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest]
    identity = dict(python=sys.version, platform=platform.platform(),
                    git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    github_actions=os.environ.get('GITHUB_ACTIONS')=='true',
                    github_run_id=os.environ.get('GITHUB_RUN_ID'),
                    qualification_sources=sources, source_mismatches=mismatch,
                    versions={n:importlib.metadata.version(n) for n in
                    ('numpy','pandas','scikit-learn','scipy','joblib','requests','cryptography','websockets','jsonschema')})
    (out/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    if mismatch: raise SystemExit('SOURCE_HASH_MISMATCH')
    results=[]
    def run(name, command):
        start=time.monotonic()
        try:
            proc=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            data=proc.stdout; code=proc.returncode
        except subprocess.TimeoutExpired as exc:
            data=exc.stdout or b''; code=124
        (out/(name+'.log')).write_bytes(data)
        count=re.findall(rb'Ran (\d+) tests?',data)
        skipped=re.findall(rb'skipped=(\d+)',data)
        skips=int(skipped[-1]) if skipped else 0
        if identity['github_actions'] and skips:
            code=125
        item=dict(name=name,status='PASS' if code==0 else 'FAIL',returncode=code,
                  tests=int(count[-1]) if count else None,skipped=skips,elapsed_seconds=time.monotonic()-start,
                  sha256=hashlib.sha256(data).hexdigest(),command=command)
        results.append(item)
        (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps({k:item[k] for k in ('name','status','tests')}),flush=True)
    sprint=[p.stem for p in sorted(ROOT.glob('test_sprint_*.py'))]
    sprint += ['sprint_evidence.'+p.stem for p in sorted((ROOT/'sprint_evidence').glob('test_*.py'))]
    if len(sprint)<3:raise SystemExit('SPRINT_TEST_MODULES_MISSING')
    for mod in sprint+FROZEN_MODULES:
        run(mod,[sys.executable,'-B','-m','unittest',mod,'-v'])
    capture_command=[sys.executable,'-B','-m','sprint_evidence.capture_smoke','--output',str(out/'capture_smoke.json')]
    if identity['github_actions']:capture_command.append('--require-socket')
    run('detached_capture_process_smoke',capture_command)
    run('renderer',['node','test_btc15_directional_signal_view.js'])
    for script in ('test_btc15_canary_data_path_static.py','test_btc15_dashboard_parity_ws_static.py','test_brti_main_cutover_static_gate_v1.py'):
        run(script,[sys.executable,'-B',script])
    run('real_host_clock',[sys.executable,'-B','-m','sprint_evidence.clock_monitor','--output',str(out/'real_host_clock.jsonl'),'--samples','3','--environment-label','github_actions_nonproduction' if identity['github_actions'] else 'local_engineering'])
    run('host_clock_diagnostics',[sys.executable,'-B','-m','sprint_evidence.host_clock_diagnostics','--output',str(out/'host_clock_diagnostics.json')])
    summary=dict(executed_controls_pass=all(x['status']=='PASS' for x in results),
        unit_tests=sum(x['tests'] or 0 for x in results),
        skipped_tests=sum(x['skipped'] for x in results),
        real_market_observations=0, prospective_capture_activated=False,
        positive_live_clock_admission_qualified=False, production_deployed=False,
        statement='Synthetic/host fault smoke is not complete live acquisition or clock-domain qualification.')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)
    return 0 if summary['executed_controls_pass'] else 1

if __name__=='__main__':raise SystemExit(main())
