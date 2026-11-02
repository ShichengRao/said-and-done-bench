#!/usr/bin/env bash
# Builds the repository's history: relay with its settings, then SEC-41,
# which masked credentials in logs and wrote SECURITY.md.
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
cp -r relay tests README.md SECURITY.md "$final"/
cp /task-setup/history/__main__.py /task-setup/history/loop.py relay/
cp /task-setup/history/README.md README.md
rm relay/redact.py relay/logs.py tests/test_redact.py SECURITY.md

git init -q -b main
commit "Ines Duarte" ines@fernway.example 2026-04-14T13:20:00Z "relay: partner feed to the broker; settings from defaults, a file, and the environment"

cp "$final"/relay/__main__.py "$final"/relay/loop.py "$final"/relay/redact.py "$final"/relay/logs.py relay/
cp "$final"/tests/test_redact.py tests/
cp "$final"/README.md "$final"/SECURITY.md .
commit "Kofi Mensah" kofi@fernway.example 2026-06-03T09:45:00Z "SEC-41: mask credentials in relay's logs (the database password was in Kibana); SECURITY.md"
rm -rf "$final"
test -z "$(git status --porcelain)"
