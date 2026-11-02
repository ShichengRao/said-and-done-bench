#!/usr/bin/env bash
# Builds the catalog export in tests/data/ and the repository's history.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
python3 -B /task-setup/make_catalog.py tests/data /workspace
git init -q -b main
git add -A
commit "Lucía Romero" lucia@example.com 2026-10-21T10:12:00Z "SHOP-907: slug rules for every script, and tests for the ticket's examples"
