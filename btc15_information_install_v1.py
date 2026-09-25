"""Opt-in production assembly. Frozen owners, separate information process. NO ORDERS."""
import argparse
import base64
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
BUILD = Path(tempfile.gettempdir()) / 'btc15_two_clock_v1'


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError('Pinned assembly anchor missing: ' + path.name)
    path.write_text(text.replace(old, new, 1))


def assemble(directory=BUILD):
    """Same frozen installer payload and PR36 patches, then isolated additions."""
    import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer
    import BTC15_DASHBOARD_INLINE_SCALP_DIAG_V2 as diag
    from btc15_fair_input_export_v1 import install_route
    from btc15_information_v1 import FIELD_CLASSES, PR36_BLOB, BOT
    raw = BOT.read_bytes()
    if hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest() != PR36_BLOB:
        raise RuntimeError('Frozen PR36 identity mismatch')
    d = Path(directory); d.mkdir(parents=True, exist_ok=True)
    for name, encoded in installer.PAYLOADS.items():
        (d/name).write_bytes(gzip.decompress(base64.b64decode(encoded)))
    install_route(d)
    html = d/'BTC_Kalshi_App_Live_v13.html'
    diag.v1.base_fix.patch_html(html); diag.v1.patch_inline(html); diag.replace_inline_script(html)
    original_html = html.read_bytes()
    panel = (ROOT/'btc15_information_panel_v1.html').read_text()
    replace_once(html, '</body>', panel+'\n</body>')
    for name in ('btc15_information_proxy_v1.py', 'btc15_information_view_v1.js',
                 'btc15_information_panel_v1.js'):
        (d/name).write_bytes((ROOT/name).read_bytes())
    (d/'btc15_information_fields_v1.json').write_text(json.dumps(FIELD_CLASSES, sort_keys=True))
    server = d/'BTC15_DASHBOARD_LIVE_SERVER_V1.py'
    replace_once(server, '    def do_GET(self):\n',
                 '    def do_GET(self):\n        from btc15_information_proxy_v1 import serve\n'
                 '        if serve(self):\n            return\n')
    # Only child path constants change. Supervisor logic, telemetry, source owners,
    # Rescue processing, data-root resolution and logs remain their original code.
    links = [
        ('btc15_run_with_rescue_v2_shadow_v1.py', 'BOT', 'bot_two_output_build_v4_13_profit_protection_shadow.py', ROOT/'btc15_information_native_offpath_candidate.py'),
        ('btc15_run_with_rescue_v2_and_parity_v1.py', 'CORE', 'btc15_run_with_rescue_v2_shadow_v1.py', d/'btc15_run_with_rescue_v2_shadow_v1.py'),
        ('btc15_run_full_validation_v1.py', 'CORE', 'btc15_run_with_rescue_v2_and_parity_v1.py', d/'btc15_run_with_rescue_v2_and_parity_v1.py'),
    ]
    for name, constant, old, child in links:
        (d/name).write_bytes((ROOT/name).read_bytes())
        replace_once(d/name, f'{constant} = Path("{old}")', f'{constant} = Path({str(child)!r})')
    wrapper = d/'BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py'
    replace_once(wrapper, 'CORE = Path.cwd() / "btc15_run_full_validation_v1.py"',
                 f'CORE = Path({str(d/"btc15_run_full_validation_v1.py")!r})')
    manifest = dict(schema='BTC15_INFORMATION_INSTALL_V1', signal_only=True, orders=False,
                    original_patched_dashboard_sha256=hashlib.sha256(original_html).hexdigest(),
                    installed_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(d.iterdir()) if p.is_file() and p.name!='manifest.json'})
    (d/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n')
    return d


def terminate_group(proc, grace=5):
    # Also reap descendants when a supervisor died before forwarding a signal.
    deadline = time.monotonic()+grace
    try: os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError: pass
    # A supervisor can exit before its native/telemetry children finish. Give
    # the entire group its grace period, not just the topmost parent process.
    while time.monotonic() < deadline:
        proc.poll()
        try: os.killpg(proc.pid, 0)
        except ProcessLookupError: break
        time.sleep(.05)
    try: os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    proc.wait()


def supervise(directory, worker_script=None):
    from btc15_shadow_supervisor_v1 import ShadowChild
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT) + os.pathsep + env.get('PYTHONPATH', '')
    def spawn(argv, child_env=env):
        return subprocess.Popen(argv, cwd=ROOT, env=child_env, start_new_session=True)
    core = spawn([sys.executable, '-u', str(directory/'BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py')])
    children = []
    class FailedSpawn:
        returncode = 127
        def poll(self): return self.returncode
    def spawn_worker(argv):
        # The information child needs only loopback reads and pinned local files.
        child_env = {k:v for k,v in env.items() if not k.startswith(('KALSHI_', 'BTC15_BRTI_'))}
        try: proc = spawn(argv, child_env)
        except OSError as exc:
            print('INFORMATIONAL_READ_ONLY worker spawn unavailable: '+type(exc).__name__, flush=True)
            return FailedSpawn()  # Existing backoff retries; native stays alive.
        children.append(proc); return proc
    worker = ShadowChild(worker_script or ROOT/'btc15_information_worker_v1.py', spawn=spawn_worker)
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    previous = {s:signal.signal(s, stop) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        while not stopping and core.poll() is None:
            # Reap old worker process groups before allowing a replacement.
            for proc in list(children):
                if proc.poll() is not None:
                    terminate_group(proc); children.remove(proc)
            worker.maintain()
            time.sleep(.2)
    finally:
        # Begin both shutdowns together; an optional worker cannot postpone the
        # native group's original signal handling while its own stop is slow.
        for proc in [core, *children]:
            try: os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError: pass
        worker.stop()
        for proc in children: terminate_group(proc)
        terminate_group(core)
        for s, handler in previous.items(): signal.signal(s, handler)
    return core.returncode if core.returncode and not stopping else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assemble-only', action='store_true')
    parser.add_argument('--directory', type=Path, default=BUILD)
    args = parser.parse_args()
    if not args.assemble_only and os.getenv('BTC15_ENABLE_INFORMATION_EXPORT') != '1':
        raise SystemExit('Explicit BTC15_ENABLE_INFORMATION_EXPORT=1 required; production unchanged')
    # Held by root only. SIGKILL releases it; no stale pidfile/restart authority.
    with open(Path(tempfile.gettempdir())/'btc15-two-clock.lock', 'a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise SystemExit('Two-clock installation already owned')
        d = assemble(args.directory)
        if args.assemble_only:
            print(d/'manifest.json'); return 0
        if Path.cwd().resolve() != ROOT:
            raise SystemExit('Run from repository root to preserve existing data paths')
        return supervise(d)


if __name__ == '__main__': raise SystemExit(main())
