#!/usr/bin/env bash
# Builds the repository's history.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

cd /workspace
git init -q -b main
git add -A
GIT_AUTHOR_NAME="Sofia Brandt" GIT_AUTHOR_EMAIL=sofia.brandt@fernhill.example GIT_AUTHOR_DATE=2026-04-09T13:20:00Z \
GIT_COMMITTER_NAME="Sofia Brandt" GIT_COMMITTER_EMAIL=sofia.brandt@fernhill.example GIT_COMMITTER_DATE=2026-04-09T13:20:00Z \
  git commit -q -m "Checkout: charge orders through PayGate"
