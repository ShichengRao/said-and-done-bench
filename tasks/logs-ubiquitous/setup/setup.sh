#!/usr/bin/env bash
# Builds the repository's history from the final files in /workspace, and
# generates samples/ and exp-worker's rotated log of the runs in logs/
# (generate.py):
#   1. 2026-01-19  the export, with a sample day for local runs (1.6.0)
#   2. 2026-03-02  retry pool timeouts with backoff (1.7.3)
#   3. 2026-05-11  drop rows the feed redelivers (1.8.0): keyed on customer, date, and total
#   4. 2026-06-22  read the feed in pages on a background thread (1.9.0)
#   5. 2026-08-27  ops' runbook for failed runs
# logs/ holds the runs from 2026-04-06 to 2026-10-21; it isn't committed.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 PYTHONDONTWRITEBYTECODE=1

commit() {  # commit NAME EMAIL DATE SUBJECT [BODY]
  git add -A
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4" ${5:+-m "$5"}
}

HISTORY=/task-setup/history
cd /workspace
final=$(mktemp -d)
cp -a /workspace/. "$final"/
find /workspace -mindepth 1 -delete
python3 /task-setup/generate.py "$final"

take() {  # take PATH...: copy final versions into the workspace
  for path in "$@"; do
    mkdir -p "$(dirname "$path")"
    cp "$final/$path" "$path"
  done
}

git init -q -b main
printf '__pycache__/\n.pytest_cache/\nout/\nlogs/\n' > .gitignore

take conftest.py exporter/__main__.py exporter/feed.py exporter/logsetup.py exporter/writer.py \
  docs/partner-format.md samples/feed-2026-01-14.csv samples/ledger-totals.csv
cp -r "$HISTORY/1/." .
commit "Dana Whitlock" dana.whitlock@fernhollow.example 2026-01-19T15:20:00Z "Nightly ledger export to Northgate"

take exporter/db.py config/export.toml tests/test_db.py
cp -r "$HISTORY/2/." .
commit "Dana Whitlock" dana.whitlock@fernhollow.example 2026-03-02T10:45:00Z "Retry pool timeouts with backoff" \
  "exp-worker's shared pool is often busy at 02:00 while the other nightly jobs start, and a single timeout failed the export. Retry up to 5 times with a growing backoff."

take exporter/dedupe.py tests/test_dedupe.py tests/test_job.py docs/ledger-feed.md README.md
cp -r "$HISTORY/3/." .
commit "Sam Okoro" sam.okoro@fernhollow.example 2026-05-11T16:05:00Z "Drop rows the feed redelivers after a replica failover" \
  "Finance found March 28's invoices double-counted at Northgate: the replica failed over that night and the feed replayed rows the export had already read. The feed is at-least-once, so drop the replays before writing the file."

take exporter/job.py exporter/prefetch.py exporter/feed.py exporter/__main__.py exporter/__init__.py \
  config/export.toml README.md tests/test_prefetch.py
commit "Dana Whitlock" dana.whitlock@fernhollow.example 2026-06-22T09:30:00Z "Read the feed in pages, on a background thread" \
  "The replica cancels queries that run past 30s, and the single query for a busy day has come close (see the slow-query warnings). Read the day in pages of 100 rows instead, on a thread so the job can start on the rows it already has, and give up with exit 3 if the feed stops sending rows; exp-worker retries those."

take docs/runbook.md
commit "Priya Raman" priya.raman@fernhollow.example 2026-08-27T14:10:00Z "docs: runbook for failed runs, from #finance-ops"

cp -r "$final/logs" logs

# Every final file is in place, everything but logs/ is committed.
(cd "$final" && find . -type f) | while read -r path; do
  cmp -s "$final/$path" "$path" || { echo "setup: $path differs from the generated workspace" >&2; exit 1; }
done
test -z "$(git status --porcelain)"
rm -rf "$final"
