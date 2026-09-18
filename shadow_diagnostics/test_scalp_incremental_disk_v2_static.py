#!/usr/bin/env python3
"""Static safety gate for disk-backed incremental adapter V2."""
import ast,pathlib
p=pathlib.Path(__file__).parents[1]/"scalp_incremental_evidence_disk_v2.py"
s=p.read_text();ast.parse(s)
for x in ["stream=True","os.replace(tmp,DATA)","X-Chunk-SHA256","X-Source-SHA256","read_only"]:
    assert x in s,x
for x in ["requests.post(","requests.put(","requests.patch(","requests.delete("]:
    assert x not in s,x
assert 'chunk_size=1024*1024' in s
assert 'cap=min(4*1024*1024' in s
print("SCALP_INCREMENTAL_DISK_V2_STATIC_TESTS_OK")
