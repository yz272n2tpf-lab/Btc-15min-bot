#!/usr/bin/env bash
# Read-only discovery of actual MAIN journal revision and deployment.
set -u
VOL=6ced6b1a-3755-4518-a240-c895e936d443
BASE=/btc15_v2_product/BTC15_V2_PRODUCT_20261004_R1
echo 'BTC15 VERIFIED MAIN DIRECTORY DISCOVERY — READ ONLY'
for p in "$BASE" "$BASE/4b33134d-d832-409e-bf35-f80689beb66b"; do
 echo "LISTING: $p"
 railway volume files --volume "$VOL" list "$p" --json
 echo "LIST RESULT: $?"
done
echo 'NO FILES DOWNLOADED OR CHANGED'
