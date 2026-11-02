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
git add -A -- . ':!ISSUES'
commit "Noor Haddad" noor@example.com 2026-09-08T14:20:00Z "fx: rate books over the rates job's daily files"
git add ISSUES
commit "Noor Haddad" noor@example.com 2026-10-22T09:10:00Z "Add FX-77"
