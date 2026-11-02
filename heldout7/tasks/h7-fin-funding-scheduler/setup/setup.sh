#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
git init -q -b main
git add -A
git -c user.name='Fictional Treasury Engineering' -c user.email='treasury@example.test' commit -qm 'Funding scheduler adapters handoff'
