#!/usr/bin/env python3
"""Read-only DOM audit for the exact packaged V13 dashboard payload."""
import base64,gzip,re
import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer

raw=gzip.decompress(base64.b64decode(installer.PAYLOADS['BTC_Kalshi_App_Live_v13.html'])).decode('utf-8','replace')
ids=sorted(set(re.findall(r'id=["\']([^"\']+)["\']',raw)))
final_ids=[x for x in ids if any(k in x.lower() for k in ('final','outcome','confidence','model'))]
# Also report code neighborhoods around FINAL-ish user-facing phrases, without modifying anything.
needles=('FINAL OUTCOME','MODEL ESTIMATE','final','confidence')
print('V13 DOM AUDIT | bytes',len(raw))
print('FINAL_IDS',final_ids)
for n in needles:
    hits=[m.start() for m in re.finditer(re.escape(n),raw,re.I)]
    print('NEEDLE',repr(n),'COUNT',len(hits))
    for i in hits[:12]:
        print(raw[max(0,i-220):i+420].replace('\n',' ')[:700])
