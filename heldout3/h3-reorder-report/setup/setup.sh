#!/usr/bin/env bash
# Builds the repository's history: stockctl, then the issue for INV-44.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
git add -A -- . ':!ISSUES'
commit "Ruth Okafor" ruth@fernway.example 2026-10-26T07:30:00Z "stockctl: products, stock, and sales from purchasing's exports (export of 2026-10-26)"
git add ISSUES
commit "Simone Berg" simone@fernway.example 2026-10-26T09:05:00Z "INV-44: write up reorder suggestions"
test -z "$(git status --porcelain)"
