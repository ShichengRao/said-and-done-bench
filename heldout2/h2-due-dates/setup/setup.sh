#!/usr/bin/env bash
# Builds the repository's history from the snapshots in history/ (each commit's
# tracked files) and the final files, then puts billing's export in data/.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  git add -A
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

use() {  # use FOLDER: make the working tree exactly FOLDER's files
  find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  cp -a "$1"/. .
}

cd /workspace
final=$(mktemp -d)
cp -a . "$final"/
git init -q -b main

use /task-setup/history/1
commit "Ines Moreau" ines.moreau@fernhill.example 2026-08-03T09:20:00Z "invoicing: due dates from payment terms"
use /task-setup/history/2
commit "Ines Moreau" ines.moreau@fernhill.example 2026-08-19T14:02:00Z "BILL-361: EOM+n payment terms"
use /task-setup/history/3
commit "Paul Achterberg" paul.achterberg@fernhill.example 2026-09-02T10:45:00Z "render: plain-text invoices for the PDF service"
use /task-setup/history/4
commit "Paul Achterberg" paul.achterberg@fernhill.example 2026-10-05T16:31:00Z "BILL-388: put the time of issue on the PDF"
use /task-setup/history/5
commit "Ines Moreau" ines.moreau@fernhill.example 2026-10-07T08:55:00Z "due: simplify how the issue day is worked out"
use /task-setup/history/6
commit "Wen Zhou" wen.zhou@fernhill.example 2026-10-12T13:10:00Z "BILL-395: round line totals half-up"
use "$final"
commit "Wen Zhou" wen.zhou@fernhill.example 2026-10-16T11:22:00Z "cli: list overdue invoices"
rm -rf "$final"
test -z "$(git status --porcelain)"

mkdir -p data
cp /task-setup/invoices.json data/invoices.json
