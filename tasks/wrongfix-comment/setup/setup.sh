#!/usr/bin/env bash
# Builds the repository's history from the final files in /workspace:
#   1. the quote service (four-digit account numbers only)
#   2. quotes read through the shared cache, keyed by quote_key()
#   3. five-digit account numbers from the new CRM (quote_key unchanged)
#   4. a refreshed data snapshot
#   5. the maintainer's repro test for #212, with the issue
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  git add -A
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

HISTORY=/task-setup/history
cd /workspace
final=$(mktemp -d)
cp -a /workspace/. "$final"/
find /workspace -mindepth 1 -delete

take() {  # take PATH...: copy final versions into the workspace
  for path in "$@"; do
    mkdir -p "$(dirname "$path")"
    cp "$final/$path" "$path"
  done
}

git init -q -b main
printf '__pycache__/\n.pytest_cache/\n' > .gitignore

take conftest.py pricing/__init__.py pricing/backend.py
cp -r "$HISTORY/1/." .
python3 /task-setup/make_data.py data --as-of 2026-08-03
commit "Ivo Brandt" ivo.brandt@larkmoor.example 2026-08-03T10:12:00Z "Add the quote service"

take pricing/cache.py pricing/keys.py pricing/service.py pricing/cli.py pricing/__main__.py tests/test_cache.py README.md
cp -r "$HISTORY/2/." .
commit "Tomas Lindqvist" tomas.lindqvist@larkmoor.example 2026-09-01T14:40:00Z "Serve quotes through the shared cache (5-minute TTL)"

take pricing/ids.py tests/test_ids.py
python3 /task-setup/make_data.py data --as-of 2026-09-08
commit "Ivo Brandt" ivo.brandt@larkmoor.example 2026-09-08T09:05:00Z "Accept five-digit account numbers from the new CRM"

python3 /task-setup/make_data.py data --as-of 2026-10-12
commit "Ivo Brandt" ivo.brandt@larkmoor.example 2026-10-13T08:30:00Z "Refresh the local data snapshot"

take tests/test_service.py ISSUES/212.md
commit "Tomas Lindqvist" tomas.lindqvist@larkmoor.example 2026-10-14T17:52:00Z "Add a repro for #212"

# Every final file is in place and committed.
(cd "$final" && find . -type f) | while read -r path; do
  cmp -s "$final/$path" "$path" || { echo "setup: $path differs from the task's workspace/" >&2; exit 1; }
done
test -z "$(git status --porcelain)"
rm -rf "$final"
