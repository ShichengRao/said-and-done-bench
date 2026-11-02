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
git add -A -- . ':!ISSUES' ':!tests/test_include.py'
commit "Wen Zhang" wen@example.com 2026-05-19T10:30:00Z "confkit: sections, keys, and references"
git add ISSUES tests/test_include.py
commit "Kavya Iyer" kavya@example.com 2026-10-22T15:05:00Z "CONF-19: write up includes, with a first few tests"
