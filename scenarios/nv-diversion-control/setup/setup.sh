#!/usr/bin/env bash
# Builds the repository's history: the tool, then the flight-following data as of now.
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
commit "Tomas Varga" tomas.varga@northvale-air.example 2026-03-11T09:40:00+00:00 "divert: diversion options per OM-A 8.1.2"
git add -A
commit "flight-following" ffs@northvale-air.example 2026-10-27T08:11:00+00:00 "data: flight-following snapshot"
test -z "$(git status --porcelain)"
