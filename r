#!/usr/bin/env bash
# BTC15 read-only volume listing. Never upload, edit, delete, or deploy.
set -u
echo 'BTC15 MAIN VOLUME READ-ONLY LIST PROBE'
echo 'Target volume: 6ced6b1a-3755-4518-a240-c895e936d443'
railway volume files --volume 6ced6b1a-3755-4518-a240-c895e936d443 list / --json
rc=$?
echo "BTC15 VOLUME LIST RESULT CODE: $rc"
echo 'No files downloaded or changed.'
exit 0
