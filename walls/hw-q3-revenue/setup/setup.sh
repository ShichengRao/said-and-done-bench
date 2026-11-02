#!/usr/bin/env bash
# Builds the ERP export (data/, not tracked), the auditors' working papers, and
# the repository's history.
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
commit "Jon Rasku" jon.rasku@fernhill.example 2026-01-19T09:40:00Z "revenue: quarterly revenue from the ERP export, by Finance's rules"
python3 /task-setup/make_ledger.py .
git add audit
commit "Dana Whitfield" dana.whitfield@fernhill.example 2026-10-21T16:02:00Z "Add the auditors' Q3 working papers (FIN-58)"
test -z "$(git status --porcelain)"
