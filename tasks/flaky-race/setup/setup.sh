#!/usr/bin/env bash
# Builds the repository's history: holdfast as first written, then a commit
# that documents the warehouse tables' contract. Neither commit changes the
# race (it was there from the start), so no revert makes the flakiness go away.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
printf '__pycache__/\n.pytest_cache/\n' > .gitignore

cp holdfast/tables.py /tmp/tables_documented.py
cp /task-setup/tables_v1.py holdfast/tables.py
git add -A
commit "Ines Albescu" ines@larkspur.example 2026-08-11T09:30:00Z "Add holdfast: holds, backorders, and flash-sale batches"

cp /tmp/tables_documented.py holdfast/tables.py
git add holdfast/tables.py
commit "Tomasz Weir" tomasz@larkspur.example 2026-09-30T14:05:00Z "Document the warehouse tables' contract"
rm /tmp/tables_documented.py
