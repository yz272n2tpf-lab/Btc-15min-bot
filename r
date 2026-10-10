#!/usr/bin/env bash
# BTC15 SSH key registration diagnostic only; no changes.
set -euo pipefail
echo 'BTC15 Railway SSH registered keys (names/fingerprints only):'
railway ssh keys list
echo 'BTC15 local SSH public key fingerprints (if any):'
find "$HOME/.ssh" -maxdepth 1 -type f -name '*.pub' -exec ssh-keygen -lf '{}' \; 2>/dev/null || true
echo 'BTC15 SSH KEY CHECK FINISHED — NO PRODUCTION ACCESS ATTEMPTED'
