#!/usr/bin/env bash
# Builds the repository's history.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
git add -A -- . ':!examples/cyclic' ':!tests/test_order.py' ':!tests/test_cli.py'
commit "Goran Horvat" goran@example.com 2026-03-03T12:00:00Z "buildgraph: build order for the monorepo's packages"
git add examples/cyclic tests
commit "Esther Cohen" esther@example.com 2026-10-24T11:40:00Z "BUILD-33: tests for the README's order rules and errors, and a cyclic example"
