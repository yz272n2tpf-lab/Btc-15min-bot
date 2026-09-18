#!/usr/bin/env python3
"""V2 manifest/delta protocol contract tests using source inspection."""
import ast,pathlib
p=pathlib.Path(__file__).parents[1]/"scalp_incremental_evidence_disk_v2.py"
s=p.read_text();ast.parse(s)
must=[
 '"/research/path-manifest"',
 '"/research/path-delta"',
 '"X-Start-Offset"',
 '"X-End-Offset"',
 '"X-Chunk-SHA256"',
 '"X-Source-Size"',
 '"X-Source-SHA256"',
 '"invalid_offset"',
 '"read_only"',
]
for x in must: assert x in s,x
assert 'self.send_response(200)' in s
assert 'self.j(409' in s
print("SCALP_INCREMENTAL_DISK_V2_PROTOCOL_TESTS_OK")
