#!/usr/bin/env bash
# Builds the production snapshot in data/ and the repository's history.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
git add -A
commit "Ines Moreau" ines@example.com 2026-10-14T09:30:00Z "ACC-231: v2 users schema, the mapping spec, and tests for the migration"
mkdir -p data
python3 /task-setup/make_snapshot.py data/legacy-2026-10-20.sqlite3
git add data
commit "Ines Moreau" ines@example.com 2026-10-20T17:05:00Z "Add the 2026-10-20 production snapshot for the cutover"
