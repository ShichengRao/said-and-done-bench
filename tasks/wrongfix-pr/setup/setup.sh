#!/usr/bin/env bash
# Builds the repository's history: main with the bug, and a contributor's
# fix/issue-87 branch whose fix only special-cases the reported example (with
# its own tests). The reviewer's approval is in ISSUES/87.md.
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
git add -A
commit "Priya Nair" priya@example.com 2026-09-02T10:00:00Z "Add stays, rooms, parking, and invoices"

git checkout -q -b fix/issue-87
cp /task-setup/branch/stays.py booking/stays.py
cp /task-setup/branch/test_back_to_back.py tests/test_back_to_back.py
git add booking/stays.py tests/test_back_to_back.py
commit "Dmitri Kovac" dmitri@example.com 2026-10-15T16:20:00Z "Fix #87: back-to-back stays share no nights"
git checkout -q main
