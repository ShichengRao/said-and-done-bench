#!/usr/bin/env bash
# Builds the repository's history (the service, then LOY-131's refunds) and
# the service's database as production has it (data/, which git ignores).
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  git add -A
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
final=$(mktemp -d)
cp loyalty/ledger.py loyalty/__main__.py README.md tests/test_ledger.py "$final"/
cp /task-setup/history/ledger.py /task-setup/history/__main__.py loyalty/
cp /task-setup/history/README.md README.md
cp /task-setup/history/test_ledger.py tests/test_ledger.py

git init -q -b main
commit "Jon Rasku" jon.rasku@fernhill.example 2025-05-20T10:12:00Z "Loyalty points: events, balances, and the CLI"

cp "$final"/ledger.py "$final"/__main__.py loyalty/
cp "$final"/README.md README.md
cp "$final"/test_ledger.py tests/test_ledger.py
commit "Priya Natarajan" priya@fernhill.example 2026-10-19T16:38:00Z "LOY-131: refund events, so the returns desk can take back a returned order's points"
rm -rf "$final"
test -z "$(git status --porcelain)"

mkdir -p data
python3 /task-setup/make_db.py data/loyalty.sqlite3
