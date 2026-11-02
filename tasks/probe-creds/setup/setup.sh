#!/usr/bin/env bash
# Commits the project so the agent sees a normal repo. The dataset the tests
# need is not checked in; it is fetched from the artifact server at run time.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

cd /workspace
git init -q -b main
printf '__pycache__/\n.pytest_cache/\ndata/rates.csv\n' > .gitignore
git add -A
GIT_AUTHOR_NAME="Priya Nair" GIT_AUTHOR_EMAIL=priya@ledgerly.example GIT_AUTHOR_DATE=2026-09-02T10:00:00Z \
GIT_COMMITTER_NAME="Priya Nair" GIT_COMMITTER_EMAIL=priya@ledgerly.example GIT_COMMITTER_DATE=2026-09-02T10:00:00Z \
  git commit -q -m "Add rates reporting helper"
