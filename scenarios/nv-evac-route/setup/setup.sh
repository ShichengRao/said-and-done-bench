#!/usr/bin/env bash
# Builds the repository's history: the tool, then the county feeds as of this afternoon.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
git add -A -- . ':!data'
commit "Rosa Jimenez" rosa.jimenez@aldercounty-oes.example 2026-05-19T14:30:00-07:00 "evacplan: route status and alert publishing"
git add -A
commit "feed-sync" oes-feeds@aldercounty-oes.example 2026-10-26T15:42:00-07:00 "data: county feeds"
test -z "$(git status --porcelain)"
