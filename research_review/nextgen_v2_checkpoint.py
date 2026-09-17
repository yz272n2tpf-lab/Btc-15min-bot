#!/usr/bin/env python3
"""Capture one frozen V2 snapshot, build a sealed review pack, or verify offline.

No collector mutations, schedules, order endpoints, policy tuning or promotion.
Hashes detect drift; this is not a signed attestation or certification result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import nextgen_v2_causal_audit as causal
import nextgen_v2_decision_ledger as ledger
import nextgen_v2_execution_costs as costs
import nextgen_v2_longitudinal as longitudinal
import nextgen_v2_review as review

VERSION = 'NEXTGEN_V2_CHECKPOINT_PACK_1'
DIRECTORY = Path(__file__).resolve().parent
TOOL_NAMES = (
    'nextgen_v2_checkpoint.py', 'nextgen_v2_review.py', 'nextgen_v2_longitudinal.py',
    'nextgen_v2_execution_costs.py', 'nextgen_v2_decision_ledger.py', 'nextgen_v2_causal_audit.py',
)
BASE_ARTIFACTS = {
    'bundle.json', 'experiment.json', 'review.json', 'review.md', 'ledger.json', 'ledger.md',
    'stress.json', 'stress.md', 'scorecard.json', 'scorecard.md',
    'mechanisms.json', 'mechanisms.md', 'summary.md',
}
MAX_HISTORY = 256
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_PACK_BYTES = 256 * 1024 * 1024
SAFETY = {'orders': False, 'automatic_promotion': False, 'same_sample_promotion': False,
          'winner_selected': False, 'certification_passed': False, 'live_raw_tape_audited': False}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def decode(raw):
    def no_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def reject_constant(_):
        raise ValueError('Non-finite JSON number')
    return json.loads(raw, object_pairs_hook=no_duplicate_keys, parse_constant=reject_constant)


def read_bytes(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Symlink inputs are not supported')
    with path.open('rb') as handle:
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError('Evidence file exceeds size limit')
    return data


def read_json(path):
    return decode(read_bytes(path))


def tool_hashes():
    return {name: sha(read_bytes(DIRECTORY / name)) for name in TOOL_NAMES}


def history_name(index):
    return f'history_{index + 1:04d}.json'


def expected_artifacts(history_count):
    if type(history_count) is not int or not 0 <= history_count <= MAX_HISTORY:
        raise ValueError('Invalid checkpoint history count')
    return BASE_ARTIFACTS | {history_name(i) for i in range(history_count)}


def validate_inputs(bundle, history, manifest):
    if not isinstance(history, list) or len(history) > MAX_HISTORY:
        raise ValueError('Invalid checkpoint history')
    for item in [*history, bundle]:
        if not isinstance(item, dict) or item.get('manifest') != manifest:
            raise ValueError('Embedded experiment manifest mismatch')
        if review.validate(item, manifest):
            raise ValueError('Invalid snapshot; no evidence pack produced')
    # Chronology is checked in actual UTC as well as by the existing history tool.
    times = [review.timestamp(item['captured_utc']) for item in [*history, bundle]]
    if any(left >= right for left, right in zip(times, times[1:])):
        raise ValueError('History must be unique and strictly chronological')
    if longitudinal.validate_series([*history, bundle], manifest):
        raise ValueError('Historical evidence changed; no pack produced')


def summary(snapshot, mechanism, history_count):
    return '\n'.join([
        '# V2 checkpoint evidence pack', '',
        f"Captured UTC: {snapshot['captured_utc']}",
        f"Market sample: **{snapshot['future_full_contracts']} full contracts / {snapshot['serial_signals']} serial opportunities**.",
        f"Remaining to review floor: {snapshot['remaining_full_contracts']} contracts / {snapshot['remaining_serial_signals']} signals.",
        f"History checkpoints: {history_count + 1}. Current comparisons: {len(snapshot['comparisons'])}.",
        f"Synthetic mechanism checks: {mechanism['checks']}; failures: {mechanism['failure_count']}.", '',
        'The market reports all use bundle.json. Synthetic mechanism tests are separate engineering evidence, not extra market observations.', '',
        '## Contents', '',
        '- review: policy comparisons, coverage and unresolved outcomes.',
        '- ledger: per-opportunity actions and exported reasons; missing reasons stay unknown.',
        '- stress: unchanged extra-cost sensitivity grid; not a manual-fill simulator.',
        '- scorecard: cumulative history without double-counting.',
        '- mechanisms: frozen-source synthetic causal/boundary tests; no live raw-path claim.',
        '- pack.json: artifact hashes, report-code hashes and the frozen experiment identity.', '',
        'COMPLETE is written last and seals pack.json. It means the evidence pack was fully written, not that a strategy is approved.',
        'Hashes are reproducibility checks, not signatures or proof of trustworthy source timestamps. Verification also re-renders every report offline with matching report code.', '',
        '## CURRENT STATE', '',
        '- CONTROL: No collector writes, restarts or deployment changes by this command.',
        '- NEW SHADOW: Existing frozen V2 evidence reviewed; all report generation is undeployed.',
        '- BLOCKED: Overall floor is not per-lane sufficiency, efficacy or certification; raw live causal paths remain unavailable.',
        '- NEXT STEP: Review a later coherent snapshot without altering frozen policies. No orders or promotion.',
    ]) + '\n'


def build_files(bundle, history, manifest):
    sources_before = tool_hashes()
    original_inputs = {'bundle': bundle, 'history': history, 'manifest': manifest}
    canonical_inputs = encode(original_inputs)
    before = sha(canonical_inputs)
    # JSON object ordering must not alter lane/report ordering after disk replay.
    normalized = decode(canonical_inputs)
    bundle, history, manifest = (normalized[name] for name in ('bundle', 'history', 'manifest'))
    validate_inputs(bundle, history, manifest)
    if causal.fingerprint() != manifest['code_sha256']:
        raise ValueError('Local collector code is not the frozen revision')
    snapshot = review.build_review(bundle, manifest)
    decisions = ledger.build_ledger(bundle, manifest)
    stress = costs.build_report(bundle, manifest)
    scorecard = longitudinal.build_series([*history, bundle], manifest)
    mechanisms = causal.run_audit(manifest)
    if not (snapshot['valid_snapshot'] and decisions['valid_snapshot'] and stress['valid_snapshot']
            and scorecard['valid_series'] and mechanisms['status'] == 'MECHANISM_TESTS_PASS'):
        raise ValueError('A report failed; no complete evidence pack produced')
    identity = (bundle['captured_utc'], bundle['state']['window_id'], bundle['state']['source_sha256'])
    for result in (snapshot, decisions, stress):
        if (result['captured_utc'], result['window_id'], result['source_sha256']) != identity:
            raise ValueError('Reports refer to different snapshots')
    latest = scorecard['checkpoints'][-1]
    if (latest['captured_utc'], scorecard['window_id'], latest['source_sha256']) != identity:
        raise ValueError('History endpoint does not match current snapshot')
    for result in (snapshot, decisions, stress, scorecard, mechanisms):
        for name in ('orders', 'automatic_promotion', 'same_sample_promotion', 'winner_selected'):
            if result.get(name) is not False:
                raise ValueError('Unsafe report flag')
    if sha(encode(normalized)) != before or sha(encode(original_inputs)) != before:
        raise ValueError('Report generation mutated its inputs')
    objects = {'bundle.json': bundle, 'experiment.json': manifest, 'review.json': snapshot,
               'ledger.json': decisions, 'stress.json': stress, 'scorecard.json': scorecard,
               'mechanisms.json': mechanisms,
               **{history_name(i): item for i, item in enumerate(history)}}
    files = {name: encode(value) for name, value in objects.items()}
    renderings = {'review.md': review.markdown(snapshot), 'ledger.md': ledger.markdown(decisions, manifest),
                  'stress.md': costs.markdown(stress), 'scorecard.md': longitudinal.markdown(scorecard),
                  'mechanisms.md': causal.markdown(mechanisms), 'summary.md': summary(snapshot, mechanisms, len(history))}
    files.update({name: value.encode() for name, value in renderings.items()})
    if set(files) != expected_artifacts(len(history)):
        raise ValueError('Pack artifact inventory mismatch')
    if any(len(raw) > MAX_FILE_BYTES for raw in files.values()) or sum(map(len, files.values())) > MAX_PACK_BYTES:
        raise ValueError('Evidence pack exceeds size limit')
    if tool_hashes() != sources_before:
        raise ValueError('Report code changed during capture')
    receipt = {'pack_version': VERSION, 'status': 'EVIDENCE_PACK_COMPLETE', **SAFETY,
               'captured_utc': identity[0], 'window_id': identity[1], 'source_sha256': identity[2],
               'collector_code_sha256': manifest['code_sha256'], 'collector_commit': manifest['commit'],
               'runtime_python': platform.python_version(), 'history_count': len(history),
               'report_code_sha256': sources_before,
               'artifacts': {name: sha(raw) for name, raw in sorted(files.items())},
               'history_is_cumulative_not_summed': True,
               'mechanisms_are_synthetic_not_market_evidence': True}
    files['pack.json'] = encode(receipt)
    files['COMPLETE'] = (sha(files['pack.json']) + '\n').encode()
    return files


def write_pack(directory, files):
    directory = Path(directory)
    receipt = decode(files['pack.json'])
    names = expected_artifacts(receipt.get('history_count'))
    if set(files) != names | {'pack.json', 'COMPLETE'}:
        raise ValueError('Unsafe or incomplete write inventory')
    if files['COMPLETE'] != (sha(files['pack.json']) + '\n').encode():
        raise ValueError('Invalid completion seal')
    # Exclusive directory and file creation; never overwrite or delete old packs.
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        if name == 'COMPLETE':
            continue
        with (directory / name).open('xb') as handle:
            handle.write(raw)
    with (directory / 'COMPLETE').open('xb') as handle:
        handle.write(files['COMPLETE'])


def verify_pack(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Expected a real evidence-pack directory')
    raw_receipt = read_bytes(directory / 'pack.json')
    receipt = decode(raw_receipt)
    if not isinstance(receipt, dict) or receipt.get('pack_version') != VERSION or receipt.get('status') != 'EVIDENCE_PACK_COMPLETE':
        raise ValueError('Invalid pack receipt')
    names = expected_artifacts(receipt.get('history_count'))
    if not isinstance(receipt.get('artifacts'), dict) or set(receipt['artifacts']) != names:
        raise ValueError('Unsafe or incomplete artifact inventory')
    if {path.name for path in directory.iterdir()} != names | {'pack.json', 'COMPLETE'}:
        raise ValueError('Missing or unexpected pack files')
    if read_bytes(directory / 'COMPLETE') != (sha(raw_receipt) + '\n').encode():
        raise ValueError('Missing or invalid completion seal')
    if any(receipt.get(key) is not value for key, value in SAFETY.items()):
        raise ValueError('Unsafe pack flag')
    if receipt.get('report_code_sha256') != tool_hashes():
        raise ValueError('Different report code; use the saved report revision')
    if receipt.get('runtime_python') != platform.python_version():
        raise ValueError('Different Python runtime; use the recorded runtime for exact replay')
    files = {}
    total = 0
    for name in sorted(names):
        raw = read_bytes(directory / name)
        total += len(raw)
        if total > MAX_PACK_BYTES or sha(raw) != receipt['artifacts'][name]:
            raise ValueError('Artifact digest or size mismatch')
        files[name] = raw
    bundle = decode(files['bundle.json'])
    manifest = decode(files['experiment.json'])
    history = [decode(files[history_name(i)]) for i in range(receipt['history_count'])]
    # Rebuilding, not just checking mutable hashes, catches forged/resealed output.
    rebuilt = build_files(bundle, history, manifest)
    for name in names:
        if files[name] != rebuilt[name]:
            raise ValueError('Report differs from independent offline replay: ' + name)
    if raw_receipt != rebuilt['pack.json']:
        raise ValueError('Receipt differs from recomputed provenance')
    return {'status': 'VERIFIED_REPRODUCIBLE_PACK', 'files': len(names) + 2,
            'captured_utc': receipt['captured_utc'], 'history_count': receipt['history_count'], **SAFETY}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    capture = commands.add_parser('capture', help='One coherent live capture, or offline bundle replay')
    capture.add_argument('--bundle', type=Path, help='Offline current bundle; omit for live GET capture')
    capture.add_argument('--history', nargs='*', type=Path, default=[], help='Explicit chronological prior bundles')
    capture.add_argument('--manifest', type=Path, default=review.MANIFEST_PATH)
    capture.add_argument('--output', type=Path, required=True)
    verify = commands.add_parser('verify', help='Read-only offline hash and report replay checks')
    verify.add_argument('directory', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            print(json.dumps(verify_pack(args.directory)))
            return 0
        if args.output.exists() or args.output.is_symlink():
            raise FileExistsError('Choose a new evidence-pack directory')
        manifest = read_json(args.manifest)
        history = [read_json(path) for path in args.history]
        # Fingerprint gate before live network access; never start a collector.
        if causal.fingerprint() != manifest['code_sha256']:
            raise ValueError('Local collector source drift')
        bundle = read_json(args.bundle) if args.bundle else review.coherent_capture(review.http_reader(manifest['service_url']), manifest)
        files = build_files(bundle, history, manifest)
        write_pack(args.output, files)
        verified = verify_pack(args.output)
        print(json.dumps({**verified, 'output': str(args.output.resolve()),
                          'source_mode': 'OFFLINE' if args.bundle else 'READ_ONLY_LIVE_GET'}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ImportError, OverflowError) as exc:
        # Never echo remote bodies, credential-bearing URLs or arbitrary exception strings.
        print(json.dumps({'status': 'CHECKPOINT_FAILED', 'error_type': type(exc).__name__, 'orders': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
