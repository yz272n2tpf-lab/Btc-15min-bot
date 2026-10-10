#!/usr/bin/env bash
# BTC15 SSH connection diagnostic; no deployment, DB access, or writes.
set -u
echo 'BTC15 SSH TRANSPORT DIAGNOSTIC'
echo 'Target: existing production MAIN service; command: pwd'
railway ssh --project baea4e22-d004-4434-b2c5-81a7fbc05086 --environment 61775c5d-c583-4dfc-af41-f25578856fd9 --service ab28dca6-7bea-4956-bdb9-dbb7b4c74635 -- pwd
rc=$?
echo "BTC15 SSH RESULT CODE: $rc"
if [ "$rc" -ne 0 ]; then
  echo 'SSH probe failed; no checkpoint access attempted.'
fi
exit 0
