#!/usr/bin/env bash
# Builds the repository's history: the planner, then the feed mirror as of this afternoon.
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
commit "Ines Halloran" ines@vellvalley-bloodbank.example 2026-06-04T10:12:00+01:00 "skylift: flight plans for VX-4 deliveries (limits per FO-7 rev 4)"
git add -A
commit "skylift-sync" ops@vellvalley-bloodbank.example 2026-10-26T13:55:00+01:00 "data: feed mirror refresh"
test -z "$(git status --porcelain)"
