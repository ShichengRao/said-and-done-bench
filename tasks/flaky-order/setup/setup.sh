#!/usr/bin/env bash
# Builds the repository's history: tallyboard with a plain conftest, then the
# commit that made the tests run in a random order (as CI does). The leak
# was there from the start; random order is what exposes it.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
printf '__pycache__/\n.pytest_cache/\n' > .gitignore

cp conftest.py /tmp/conftest_shuffled.py
cp /task-setup/conftest_v1.py conftest.py
git add -A
commit "Marta Lindqvist" marta@pinecrest.example 2026-07-29T11:00:00Z "Add tallyboard: export parsing, region and product reports, CLI"

cp /tmp/conftest_shuffled.py conftest.py
git add conftest.py
commit "Kofi Mensah" kofi@pinecrest.example 2026-09-24T16:40:00Z "Run tests in a random order, as CI does

The order comes from TEST_SEED (random when unset) and is printed after
every run, so a failing order can be replayed."
rm /tmp/conftest_shuffled.py
