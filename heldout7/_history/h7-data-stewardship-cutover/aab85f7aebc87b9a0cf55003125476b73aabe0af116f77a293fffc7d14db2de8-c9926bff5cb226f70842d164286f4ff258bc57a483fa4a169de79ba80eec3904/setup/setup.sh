#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
git init -q -b main
git add -A
git -c user.name='Fictional Stewardship Engineering' -c user.email='stewardship@example.test' commit -qm 'Stewardship migration handoff'
