#!/usr/bin/env python3
"""Expose generated BTC15 full-validation wrapper for regression inspection.
Offline helper only. Does not launch production and does not modify installer payload.
"""
import ast,base64,gzip
from pathlib import Path
SRC=Path(__file__).with_name("BTC15_INSTALL_LIVE_DASHBOARD_V13.py")
KEY="BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py"
def extract():
 tree=ast.parse(SRC.read_text(encoding="utf-8"))
 for node in ast.walk(tree):
  if isinstance(node,ast.Assign):
   for target in node.targets:
    if isinstance(target,ast.Name) and target.id=="PAYLOADS":
     d=ast.literal_eval(node.value)
     raw=gzip.decompress(base64.b64decode(d[KEY])).decode("utf-8")
     return raw
 raise RuntimeError("PAYLOADS not found")
def main():
 raw=extract()
 print(raw)
if __name__=="__main__":main()

# RAILWAY_REGRESSION_INSPECTION_TRIGGER_20260922
