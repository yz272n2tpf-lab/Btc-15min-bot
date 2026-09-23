"""One-time, non-destructive archive of signal datasets before cutover. NO ORDERS."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def preserve(root, label):
    root = Path(root)
    if not root.is_dir() or not label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in label):
        raise ValueError('existing dataset root and safe archive label required')
    destination = root / ('btc15-evidence-' + label + '.zip')
    if destination.exists():
        with zipfile.ZipFile(destination) as archive:
            if archive.testzip() is not None or 'manifest.json' not in archive.namelist():
                raise RuntimeError('existing evidence archive failed validation')
        return dict(status='PRESERVED_EXISTING', archive=str(destination))
    # Only known signal-data families, never environment/credential/key files.
    files = sorted(p for p in root.iterdir() if p.is_file() and not p.is_symlink()
                   and p.suffix in {'.csv', '.json'}
                   and p.name.startswith(('kalshi_', 'scalp_', 'btc15_', 'dashboard_state')))
    sizes = {p.name: p.stat().st_size for p in files}
    total = sum(sizes.values())
    if shutil.disk_usage(root).free < total * 1.02 + 10_000_000:
        raise RuntimeError('insufficient archive headroom; original evidence untouched')
    temporary = destination.with_suffix('.partial')
    if temporary.exists():
        raise RuntimeError('prior partial archive retained; inspect before retry')
    records = []
    with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path in files:
            digest = hashlib.sha256()
            remaining = sizes[path.name]
            with path.open('rb') as src, archive.open(path.name, 'w', force_zip64=True) as dst:
                while remaining:
                    chunk = src.read(min(1_048_576, remaining))
                    if not chunk:
                        raise RuntimeError('dataset truncated during archive; original retained')
                    digest.update(chunk); dst.write(chunk); remaining -= len(chunk)
            records.append(dict(name=path.name, bytes=sizes[path.name], sha256=digest.hexdigest()))
        archive.writestr('manifest.json', json.dumps(dict(
            created_utc=datetime.now(timezone.utc).isoformat(), files=records,
            snapshot_semantics='EXACT_BYTE_PREFIX_AT_START', signal_only=True, orders=False), indent=2))
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('archive validation failed; original evidence retained')
    temporary.rename(destination)
    return dict(status='PRESERVED', archive=str(destination), files=len(files), bytes=total)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True)
    parser.add_argument('--label',required=True)
    args=parser.parse_args()
    print('BTC15 EVIDENCE PRESERVED | '+json.dumps(preserve(args.root,args.label))+' | NO ORDERS',flush=True)

if __name__=='__main__': main()
