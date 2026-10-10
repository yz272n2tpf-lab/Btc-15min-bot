#!/usr/bin/env bash
# BTC15 read-only discovery of actual production revision.
set -u
VOL=6ced6b1a-3755-4518-a240-c895e936d443
BASE=/btc15_v2_product/BTC15_INTEGRATED_OFFLINE_20261006
echo 'BTC15 CURRENT REVISION PATH CHECK — READ ONLY'
railway volume files --volume "$VOL" list "$BASE" --json
echo "REVISION LIST RESULT: $?"
echo 'NO FILES DOWNLOADED OR CHANGED'
