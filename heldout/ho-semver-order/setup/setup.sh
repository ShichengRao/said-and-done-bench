#!/usr/bin/env bash
# Builds the repository's history: relkit, then the tests added for REL-58.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
git add -A -- . ':!tests'
commit "Jonas Berg" jonas@example.com 2026-04-11T08:45:00Z "relkit: latest release and changelog start from tags"
git add tests
commit "Amara Mensah" amara@example.com 2026-10-23T16:30:00Z "REL-58: tests for version ordering"
