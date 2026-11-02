#!/usr/bin/env bash
# Builds the repository's history: ledgerly and the books, then the issue for LED-12 with its samples.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
git add -A -- . ':!ISSUES' ':!samples'
commit "Jana Kowalczyk" jana@studio-feld.example 2026-09-01T18:20:00Z "ledgerly: the books, by hand"
git add ISSUES samples
commit "Jana Kowalczyk" jana@studio-feld.example 2026-10-26T09:40:00Z "LED-12: write up statement imports, with October's statements as samples"
test -z "$(git status --porcelain)"
