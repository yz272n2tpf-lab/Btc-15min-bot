#!/usr/bin/env bash
# Read-only access probe. No database operations, deployments or file changes.
set -euo pipefail
echo 'BTC15: probing existing MAIN container with pwd only'
railway ssh --project baea4e22-d004-4434-b2c5-81a7fbc05086 --environment 61775c5d-c583-4dfc-af41-f25578856fd9 --service ab28dca6-7bea-4956-bdb9-dbb7b4c74635 -- pwd
