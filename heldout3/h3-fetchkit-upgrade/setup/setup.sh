#!/usr/bin/env bash
# Builds the repository's history: notify with fetchkit 1.6.2 vendored (and
# its release tarball), then the commit that downloaded 2.0.1 for NOTIF-61.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  git add -A
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
python3 /task-setup/make_tarballs.py /task-setup/releases vendor/downloads fetchkit-1.6.2
git init -q -b main
commit "Lea Brandt" lea@fernway.example 2026-02-09T10:30:00Z "notify: order and delivery texts through Textwise, with fetchkit 1.6.2 vendored"

python3 /task-setup/make_tarballs.py /task-setup/releases vendor/downloads fetchkit-2.0.1
commit "Marco Rossi" marco@fernway.example 2026-10-22T17:05:00Z "Download fetchkit 2.0.1 for NOTIF-61"
test -z "$(git status --porcelain)"
