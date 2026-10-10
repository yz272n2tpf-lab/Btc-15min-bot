#!/usr/bin/env bash
# BTC15 read-only listing of current MAIN deployment journal files.
set -u
VOL=6ced6b1a-3755-4518-a240-c895e936d443
DIR=/btc15_v2_product/BTC15_INTEGRATED_OFFLINE_20261006/4b33134d-d832-409e-bf35-f80689beb66b
echo 'BTC15 CURRENT MAIN JOURNAL FILE INVENTORY — READ ONLY'
railway volume files --volume "$VOL" list "$DIR" --json
rc=$?
echo "BTC15 CURRENT JOURNAL LIST RESULT: $rc"
echo 'No files downloaded, written, deleted or deployed.'
exit 0
