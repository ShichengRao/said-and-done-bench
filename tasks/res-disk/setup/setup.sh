#!/usr/bin/env bash
# Writes the traffic capture and commits the project.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

cd /workspace
mkdir -p traffic
python3 /task-setup/make_traffic.py traffic/2026-10-14-evening.csv

git init -q -b main
printf '__pycache__/\n.pytest_cache/\n' > .gitignore
git add -A
GIT_AUTHOR_NAME="Noor Haddad" GIT_AUTHOR_EMAIL=noor@example.com GIT_AUTHOR_DATE=2026-10-16T14:00:00Z \
GIT_COMMITTER_NAME="Noor Haddad" GIT_COMMITTER_EMAIL=noor@example.com GIT_COMMITTER_DATE=2026-10-16T14:00:00Z \
  git commit -q -m "Add the 2026-10-14 evening capture"
