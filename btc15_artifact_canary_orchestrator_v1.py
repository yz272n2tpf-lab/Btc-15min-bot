#!/usr/bin/env python3
"""One-container builder -> certify -> fast runtime canary.
Avoids persistent volume and keeps fitted artifact private to ephemeral container.
"""
import json,os,subprocess,sys
from pathlib import Path
RAW=Path("/tmp/btc15_fitted_freeze.pkl"); ART=Path("/tmp/btc15_certified_models.pkl")
CORE="bot_two_output_build_v4_13_profit_protection_shadow.py"
env=os.environ.copy();env["BTC15_FREEZE_FITTED_MODELS_PATH"]=str(RAW);env["BTC15_FREEZE_EXIT_AFTER_EMIT"]="1";env.pop("BTC15_CERTIFIED_MODEL_ARTIFACT_PATH",None);env.pop("BTC15_CERTIFIED_MODEL_ARTIFACT_SHA256",None)
print("PHASE 1/3 PROTECTED FIT+FREEZE | NO ORDERS",flush=True)
subprocess.run([sys.executable,"-u",CORE],env=env,check=True)
print("PHASE 2/3 CERTIFY EXACT ARTIFACT",flush=True)
p=subprocess.run([sys.executable,"-u","btc15_freeze_certified_models_v1.py","--input",str(RAW),"--output",str(ART)],text=True,capture_output=True,check=True)
print(p.stdout.strip(),flush=True)
line=[x for x in p.stdout.splitlines() if "MODEL_ARTIFACT_FREEZE_PASS" in x][-1]; result=json.loads(line);sha=result["artifact_sha256"]
subprocess.run([sys.executable,"-u","btc15_certified_artifact_runtime_preflight_v1.py","--artifact",str(ART),"--sha",sha,"--parity-input",str(RAW)],check=True)
print("PHASE 3/3 FAST CERTIFIED RUNTIME | NO RETRAIN | NO ORDERS",flush=True)
env=os.environ.copy();env.pop("BTC15_FREEZE_FITTED_MODELS_PATH",None);env.pop("BTC15_FREEZE_EXIT_AFTER_EMIT",None);env["BTC15_CERTIFIED_MODEL_ARTIFACT_PATH"]=str(ART);env["BTC15_CERTIFIED_MODEL_ARTIFACT_SHA256"]=sha
os.execve(sys.executable,[sys.executable,"-u",CORE],env)
