"""Validate the proposed MAIN release manifest using the actual release verifier.

Only the in-memory candidate is written to a temporary file and then swapped
into the checkout for verification; the original checkout manifest is restored
in all cases. No production services, credentials or data are accessed.
"""
from pathlib import Path
from btc15_v2_product.release import ROOT, MANIFEST, verify_files

candidate=ROOT/'qualification'/'early-release-review'/'BTC15_V2_PRODUCT_RELEASE_R1.candidate.json'
original=MANIFEST.read_bytes()
proposed=candidate.read_bytes()
if original==proposed:
    raise SystemExit('CANDIDATE_NOT_DIFFERENT_FROM_OLD_MANIFEST')
try:
    MANIFEST.write_bytes(proposed)
    manifest=verify_files('main')
    print('MAIN_CANDIDATE_RELEASE_VALIDATED')
    print('manifest_file_count:',len(manifest['files_sha256']))
    print('protected_main_file_count:',len(manifest['lane_protected_files']['main']))
finally:
    MANIFEST.write_bytes(original)
if MANIFEST.read_bytes()!=original:
    raise SystemExit('MANIFEST_RESTORE_FAILED')
print('ORIGINAL_MANIFEST_RESTORED')
