#!/usr/bin/env bash
# Builds the repository's history from the final files in /workspace:
#   1. tidewater: monthly reports from v2 feeds, with vendored chronoparse and textable
#   2. the v3 feed spec from Harbour Operations, and Vesper Reef in the registry
#   3. November's feeds, v3 test cases, and the signed-off November outputs
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

take() {  # take PATH...: copy final versions (files, or folders' contents) into the workspace
  for path in "$@"; do
    if [ -d "$final/$path" ]; then
      mkdir -p "$path"
      cp -R "$final/$path/." "$path/"
    else
      mkdir -p "$(dirname "$path")"
      cp "$final/$path" "$path"
    fi
  done
}

git init -q -b main
printf '__pycache__/\n.pytest_cache/\n' > .gitignore
take conftest.py tidewater vendor docs/feeds.md tests/test_feeds_v2.py
mkdir -p data tests
cp "$HISTORY/stations.json" data/stations.json
cp "$HISTORY/test_report.py" tests/test_report.py
cp "$HISTORY/README.md" README.md
commit "Pavel Strand" pavel.strand@carrow-harbour.example 2025-11-03T10:20:00Z "tidewater: monthly reports from the v2 gauge feeds"

take docs/feed-v3.md data/stations.json README.md
commit "Ines Varga" ines.varga@carrow-harbour.example 2026-10-20T14:05:00Z "Add the v3 feed spec and Vesper Reef to the registry"

take data/2026-11 tests
commit "Ines Varga" ines.varga@carrow-harbour.example 2026-12-02T08:45:00Z "November's feeds, v3 test cases, and the signed-off November outputs"

# Every final file is in place and committed.
(cd "$final" && find . -type f) | while read -r path; do
  cmp -s "$final/$path" "$path" || { echo "setup: $path differs from the task's workspace/" >&2; exit 1; }
done
test -z "$(git status --porcelain)"
rm -rf "$final"
