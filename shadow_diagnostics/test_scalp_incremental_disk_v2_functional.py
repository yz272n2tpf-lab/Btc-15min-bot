#!/usr/bin/env python3
"""Local functional tests for V2 chunk serving invariants without network."""
import hashlib,os,tempfile
NL=bytes([10])
header=b"record_type,contract,value"+NL
rows=[f"event,c{i},{i}".encode()+NL for i in range(1000)]
raw=header+b"".join(rows)
fd,path=tempfile.mkstemp();os.close(fd)
try:
    open(path,"wb").write(raw)
    rebuilt=bytearray();offset=0;cap=257
    while offset<len(raw):
        with open(path,"rb") as f:
            f.seek(offset);chunk=f.read(cap)
            if offset+len(chunk)<len(raw):
                p=chunk.rfind(NL);chunk=b"" if p<0 else chunk[:p+1]
        assert chunk,("empty chunk",offset)
        sha=hashlib.sha256(chunk).hexdigest()
        assert sha==hashlib.sha256(chunk).hexdigest()
        rebuilt.extend(chunk);offset+=len(chunk)
    assert bytes(rebuilt)==raw
    assert hashlib.sha256(rebuilt).hexdigest()==hashlib.sha256(raw).hexdigest()
    assert rebuilt.count(NL)-1==len(rows)
    print("SCALP_INCREMENTAL_DISK_V2_FUNCTIONAL_TESTS_OK")
finally:
    os.unlink(path)
