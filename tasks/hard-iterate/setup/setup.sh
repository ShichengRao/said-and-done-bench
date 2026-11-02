#!/usr/bin/env bash
# Generates the benchmark data (bench/: the quick sample; bench/day/: a full
# day, kept out of git for its size) and commits the project in two steps.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 PYTHONDONTWRITEBYTECODE=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
python3 /task-setup/make_bench.py bench

git init -q -b main
printf '__pycache__/\n.pytest_cache/\n# A day of events is too big for git; CI fetches it.\nbench/day/events.jsonl.gz\n' > .gitignore
git add .gitignore conftest.py heron tests
commit "Ines Duarte" ines.duarte@heron.example 2026-09-29T10:20:00+02:00 "Add device events and dedupe"
git add -A
commit "Kofi Mensah" kofi.mensah@heron.example 2026-10-20T17:45:00+02:00 \
  "Add benchmarks for the nightly import's dedupe step"
