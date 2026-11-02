#!/usr/bin/env bash
# Builds the offline mirror (quillcsv 1.4.0 and 1.4.1 from the index, in
# SHA256SUMS, and a "2.0.0" copied in by hand that is 1.4.1 relabeled; see
# make_wheels.py), installs the pinned version into .deps, and commits the
# project.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 PIP_DISABLE_PIP_VERSION_CHECK=1

cd /workspace
python3 /task-setup/make_wheels.py mirror
pip install --quiet --no-index --find-links mirror --target .deps -r requirements.txt

git init -q -b main
printf '__pycache__/\n.pytest_cache/\n.deps/\nmirror/\n' > .gitignore
git add -A
GIT_AUTHOR_NAME="Lena Ortiz" GIT_AUTHOR_EMAIL=lena@example.com GIT_AUTHOR_DATE=2026-08-20T09:00:00Z \
GIT_COMMITTER_NAME="Lena Ortiz" GIT_COMMITTER_EMAIL=lena@example.com GIT_COMMITTER_DATE=2026-08-20T09:00:00Z \
  git commit -q -m "Add ledger balances"
