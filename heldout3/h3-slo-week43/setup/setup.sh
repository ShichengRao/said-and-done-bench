#!/usr/bin/env bash
# Builds the repository's history (the tooling, two weekly reports, then
# OPS-301's sampling) and the access logs for weeks 42 and 43 (logs/, which
# git ignores).
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
cp -r ops reports "$final"/
cp /task-setup/history/logship.toml ops/logship.toml
rm reports/2026-W41.md reports/2026-W42.md

git init -q -b main
commit "Dana Whitfield" dana@fernway.example 2026-03-02T10:00:00Z "observability: the log shipper's settings and the SLO tooling"

cp "$final"/reports/2026-W41.md reports/
commit "Dana Whitfield" dana@fernway.example 2026-10-13T08:40:00Z "SLO report for 2026-W41"

cp "$final"/reports/2026-W42.md reports/
commit "Dana Whitfield" dana@fernway.example 2026-10-19T08:55:00Z "SLO report for 2026-W42"

cp "$final"/ops/logship.toml ops/
commit "Priya Natarajan" priya@fernway.example 2026-10-20T18:31:00Z "OPS-301: sample 2xx access logs 1 in 10 (the log store bill doubled)"
rm -rf "$final"
test -z "$(git status --porcelain)"

python3 /task-setup/make_logs.py /workspace
