#!/usr/bin/env bash
# Builds the repository's history: the tool, the status board feed, then the current data.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
mv data/status_board.json /tmp/status_board.json
git init -q -b main
git add -A -- . ':!data/cases'
commit "Dana Okoro" dana.okoro@corran-ems.example 2026-03-04T16:20:00-08:00 "emsdest: destination protocol 4.2 rev 7"
cp /tmp/status_board.json data/status_board.json
git add data/status_board.json
commit "Wes Albright" wes.albright@corran-ems.example 2026-09-29T10:05:00-07:00 "CAD integration: mirror the regional status board into data/"
git add -A
commit "cad-sync" cad@corran-ems.example 2026-10-26T14:02:00-07:00 "data: refresh"
test -z "$(git status --porcelain)"
