#!/usr/bin/env bash
# BTC15 PHASE A — READ-ONLY RAILWAY/CODESPACE PREFLIGHT.
# No backup creation, downloads, restarts, deploys, or production writes.
set -u
PROJECT=baea4e22-d004-4434-b2c5-81a7fbc05086
ENV=61775c5d-c583-4dfc-af41-f25578856fd9
SERVICE=ab28dca6-7bea-4956-bdb9-dbb7b4c74635
VOL=6ced6b1a-3755-4518-a240-c895e936d443
DIR=/btc15_v2_product/BTC15_INTEGRATED_OFFLINE_20261006/4b33134d-d832-409e-bf35-f80689beb66b
echo '=== BTC15 PHASE A READ-ONLY PREFLIGHT ==='
echo '[1/4] Codespace disk space'
df -h /workspaces
echo '[2/4] Railway CLI version'
railway --version
echo '[3/4] Existing MAIN volume journal listing'
if railway volume files --volume "$VOL" list "$DIR" --json; then
  echo 'PASS: MAIN_VOLUME_FILES_ACCESS'
else
  echo 'BLOCKED: MAIN_VOLUME_FILES_ACCESS'
fi
echo '[4/4] Existing MAIN service file access to /tmp'
if railway service files --project "$PROJECT" --environment "$ENV" --service "$SERVICE" list /tmp --json; then
  echo 'PASS: MAIN_SERVICE_FILES_ACCESS'
else
  echo 'BLOCKED: MAIN_SERVICE_FILES_ACCESS'
fi
echo '=== READ-ONLY PREFLIGHT COMPLETE; NO PRODUCTION CHANGES ==='
