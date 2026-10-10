#!/usr/bin/env bash
# BTC15 read-only directory discovery on the existing MAIN volume.
set -u
VOL=6ced6b1a-3755-4518-a240-c895e936d443
echo 'BTC15 MAIN JOURNAL DIRECTORY DISCOVERY — READ ONLY'
for p in /btc15_v2_product /btc15_v2_product/BTC15_V2_PRODUCT_R1; do
  echo "LISTING: $p"
  railway volume files --volume "$VOL" list "$p" --json
  echo "LIST RESULT: $?"
done
echo 'BTC15 DISCOVERY FINISHED — NO FILES DOWNLOADED OR CHANGED'
