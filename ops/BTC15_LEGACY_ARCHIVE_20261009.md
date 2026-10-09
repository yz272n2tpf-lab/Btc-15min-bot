# Authorized MAIN legacy journal archive

Scope: only `/data/btc15_information_frames_v1.jsonl` (2,636,133,318 bytes).
Parent production commit: `b8bd240b4e27a949e7db0388b8fc9bae24d83ef5`.
Parent deployment: `2d1ca61c-51b5-415d-8cca-02ed86a7cb69`.
Project: `baea4e22-d004-4434-b2c5-81a7fbc05086`.
Environment: `61775c5d-c583-4dfc-af41-f25578856fd9`.
MAIN: `ab28dca6-7bea-4956-bdb9-dbb7b4c74635`.
Volume: `6ced6b1a-3755-4518-a240-c895e936d443`, mounted at `/data`.

## Runtime safeguards

The existing MAIN supervisor starts one nonessential maintenance process only
when `BTC15_ARCHIVE_LEGACY_ONCE=20261009`. Its failure cannot restart MAIN.
The job verifies the exact project/environment/service/volume, mount, compressed
new-record mode and original size. It waits for the existing three application
processes and health endpoint; it runs nice 19, with a 256 MiB address-space cap,
1 MiB chunks and a 10 ms yield after each compression/byte-comparison chunk.
It scans the real process namespace for open original-file writers; inability
to inspect descriptors is an abort, not permission to assume inactivity.
Inode/device/size/mtime/ctime must remain unchanged throughout every pass.

First pass streams deterministic gzip level 6 to a byte counter and SHA-256,
writing no archive. Required available space is exact compressed bytes plus
1,073,741,824 bytes operating reserve plus 67,108,864 bytes growth headroom.
The complete remaining output must continue to fit on every compression write.
Space or health failure aborts and removes only this attempt's partial output.
The original and any already published archive are retained on failures.

Second pass creates a fsynced partial gzip on the SAME durable volume. Both
compression passes must match byte counts, newline record counts, raw SHA-256,
compressed size and compressed SHA-256. Complete decompression is also compared
byte-for-byte with the still-open original. A no-overwrite hard link publishes
`/data/btc15_information_frames_v1.jsonl.gz`; the partial name is unlinked and
the directory fsynced. The complete existing historical line reader must then
return the original byte count, record count and SHA-256 from the archive.

A durable VERIFIED receipt precedes original removal. Only after another file
identity, no-writer, service-health and reserve check is the redundant original
unlinked and the directory fsynced. Its open descriptor is closed to free blocks.
The normal historical-reader fallback is then streamed through every legacy
record again, matching the original digest and record count. COMPLETED includes
actual file/block recovery and remaining filesystem free bytes.

Receipt: `/data/btc15_information_frames_v1.jsonl.archive-20261009.receipt.json`.
Durable `.archive-20261009.attempt` and `.lock` files prevent repeat attempts.
Do not delete these to retry an abort without investigating its logged cause.

## Reader and restart continuity

The historical reader prefers the original while both representations exist,
otherwise opens its `.gz` fallback, then reads all existing new-record segments.
An explicit `.gz` input is also supported. There is never a double read of the
plain and compressed representations. Segment last-write times order the
single-writer sessions across restarts; random filename suffixes cannot do so.
No new-record writer or segment bytes are modified.

Only the two predecessor identity constants in the EXISTING EARLY restart
handoff are updated to the parent build/deployment above. Its existing validation,
checkpoint transfer, source freshness, protection latches and missing-path
handling are unchanged. No publication is imported or made newly actionable.
No FINAL, EARLY, SCALP, reversal or dashboard presentation logic changes.
COCKPIT/SCALP are not deployed. The unrelated staged Railway patch is untouched.

## Restoration and rollback

Disabling future maintenance needs only omission of `BTC15_ARCHIVE_LEGACY_ONCE`
from the start command. It is one attempt even if that flag remains present.
Do not roll back to a reader without gzip support while the plain file is absent.
The safest operational rollback retains this compatible reader and disables the
maintenance opt-in; this does not reverse the lossless archive.

For exact plain-file restoration, run the following inside MAIN's mounted volume
under a separately reviewed operational execution. It requires original size plus
the same reserve/headroom, preserves the archive, refuses to overwrite a file,
and verifies the full restored file before publishing its original name:

```python
import gzip, hashlib, json, os, shutil
from pathlib import Path
p = Path('/data/btc15_information_frames_v1.jsonl')
r = json.loads(Path(str(p)+'.archive-20261009.receipt.json').read_text())
archive = Path(str(p)+'.gz')
temporary = Path(str(p)+'.restore.partial')
reserve = 1024**3 + 64*1024**2
assert r['status'] == 'COMPLETED' and not p.exists() and not temporary.exists()
assert shutil.disk_usage(p.parent).free >= r['bytes'] + reserve
h = hashlib.sha256(); size = count = 0
with gzip.open(archive, 'rb') as src, temporary.open('xb') as dst:
    os.chmod(temporary, 0o600)
    while True:
        block = src.read(1024**2)
        if not block: break
        assert shutil.disk_usage(p.parent).free >= r['bytes']-size+reserve
        dst.write(block); h.update(block); size += len(block); count += block.count(b'\n')
    dst.flush(); os.fsync(dst.fileno())
assert (size, count, h.hexdigest()) == (r['bytes'], r['records'], r['sha256'])
h = hashlib.sha256(); size = count = 0
with temporary.open('rb') as src:
    while True:
        block = src.read(1024**2)
        if not block: break
        h.update(block); size += len(block); count += block.count(b'\n')
assert (size, count, h.hexdigest()) == (r['bytes'], r['records'], r['sha256'])
os.link(temporary, p)  # fails safely if original name reappeared
temporary.unlink()
fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
os.fsync(fd); os.close(fd)
print('RESTORED', size, count, h.hexdigest(), 'archive retained')
```

If restoration aborts, leave archive and partial intact and investigate; never
overwrite or delete the archive. Both representations are safe with this reader.
After successful restoration, the exact previous MAIN source is the parent
commit above on branch `fix/btc15-live-infrastructure-20261009`. Its manifest
SHA-256 is `5b774e3c393d7ed785da19a8d52ced3548eda1275fb9c4115c7c16387d43b813`.
Its exact start command was:

```sh
/bin/sh -c 'test "$RAILWAY_VOLUME_MOUNT_PATH" = "/data" && test -n "$RAILWAY_VOLUME_ID" && unset BTC15_LADDER_DATA_ROOT && export BTC15_V2_APPROVED_BUILD=b8bd240b4e27a949e7db0388b8fc9bae24d83ef5 BTC15_V2_APPROVED_MANIFEST_SHA256=5b774e3c393d7ed785da19a8d52ced3548eda1275fb9c4115c7c16387d43b813 && exec python -u btc15_v2_launch.py --lane main --run-reviewed-production'
```

Any code rollback that allocates a new deployment must likewise carry its actual
current EARLY predecessor or occur with no active origin; the old build hardcodes
an older predecessor. Do not blindly restart that build across an active origin.

## Focused verification

Small local fixtures cover lossless roundtrip, exact compression size, real
historical reader order/no duplicates, low space before/during output, active
writers, changing originals, corruption, reader failure, existing archives,
unreadable process descriptors and one-attempt behavior. The existing EARLY
handoff regression verifies preservation of a live origin without old publication.
Both frozen lane identities, release manifest and MAIN assembly are checked.
These are file-safety gates, not a live trading test campaign.

## Completed production result

MAIN deployment `a73609f5-4d62-4f97-8513-17b0566d6811` reached SUCCESS on
commit `6cc77cf1c0f8a30db52e3538614bc9c95662516c`.
The archive completed at 2026-10-09 03:38:23 UTC (October 8, 11:38:23 p.m. EDT).

| Measurement | Bytes |
|---|---:|
| Original | 2,636,133,318 |
| Durable gzip archive | 208,849,896 |
| Net logical file storage recovered | 2,427,283,422 |
| Allocated filesystem blocks recovered | 2,427,293,696 |
| Filesystem free after completion | 3,806,130,176 |

All 1,460,029 newline-delimited records and their original byte order match.
Raw, fully decompressed, explicit archive reader, and normal fallback reader
SHA-256: `da4050b69b35f479aa7264bf145f5de6e350f303498556de959e9f1abfbcb1a8`.
Compressed SHA-256: `946506518c1c9d71f2bfc5e44199b6ed7afd36ce7bb089812516488a3910d203`.
The exact dry-run size matched the actual compressed file. Before writing,
1,383,890,944 bytes were free versus 1,349,700,584 required including reserves.
Only the verified redundant plain representation was removed.

Railway's later disk metric is 6.317719552 GB used of the existing 10 GB limit
(approximately 3.682 GB nominal headroom). Platform and mounted-filesystem
measurements differ; the filesystem figure above is the actual available-space
measurement used by the archive. No capacity purchase was made.

All six bounded post-completion endpoint checks returned HTTP 200: MAIN health,
MAIN ladders/information, and COCKPIT information/MAIN/SCALP ladders. Information
was AVAILABLE, with current contract identity, on both MAIN and COCKPIT.
The genuine active EARLY origin `f49b0010bac27ed87c93bbe0db6bdce14a5d97e488ecf0112ea74277fecea8a2`
was carried from the previous deployment and progressed from WATCH to PROTECT.
MAIN journal sequence advanced to 77 with zero drops and queue depth zero;
SCALP remained AVAILABLE on its unchanged build with zero drops and queue depth
zero. FINAL remained its genuine PASS decision. No trading decision was forced.

The one-time opt-in was removed from MAIN's saved next-start command after success,
without another restart. The durable attempt marker also prevents repeats.
COCKPIT remains `7a0b661291743222c1f6ac30df8b42e274fd6c73`; SCALP remains
`f9ef31a03662af74b0aa1bb0640f8eb49523fdb8`. The unrelated four-change staged
patch `ead9997e-b5b7-4668-a612-e8417e197838` remains unapplied and unchanged.

The complete production receipt and endpoint evidence are in
`evidence/archive_20261009/result.json`, as well as the archive receipt on `/data`.
This result-only documentation update does not alter the pinned live build.
