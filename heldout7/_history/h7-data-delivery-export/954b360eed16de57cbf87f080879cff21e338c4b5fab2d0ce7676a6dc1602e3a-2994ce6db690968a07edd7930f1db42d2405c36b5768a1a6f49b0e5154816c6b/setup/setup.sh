#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
git init -q -b main
git add -A
git -c user.name='Fictional Delivery Engineering' -c user.email='delivery@example.test' commit -qm 'Delivery exporter handoff'
