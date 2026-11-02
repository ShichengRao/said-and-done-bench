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
git add -A -- . ':!docs' ':!examples/inv-881.csv' ':!examples/three.csv'
commit "Tomasz Nowak" tomasz@example.com 2026-07-01T09:00:00Z "costsplit: split invoices across cost centers"
git add docs examples
commit "Helga Bauer" helga@example.com 2026-10-20T13:25:00Z "Write down how splits work (finance's rules), with the BILL-204 examples"
