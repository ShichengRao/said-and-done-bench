#!/usr/bin/env bash
# Builds the repository's history (the engine, the metrics doc, the jobqueue
# 2.0 dashboards, the TLS rule) and the recorded metrics in data/.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
final=$(mktemp -d)
cp -R alerts/rules.toml README.md docs dashboards "$final"/
rm -rf docs dashboards
cp /task-setup/history/rules.toml alerts/rules.toml
cp /task-setup/history/README.md README.md

git init -q -b main
git add -A
commit "Lena Ortiz" lena.ortiz@fernhill.example 2026-01-20T10:05:00Z "opsalerts: alert rules, the evaluation engine, and replay"

cp -R "$final"/docs docs
git add docs
commit "Lena Ortiz" lena.ortiz@fernhill.example 2026-02-03T15:30:00Z "docs: the metrics our services export"

cp -R "$final"/dashboards dashboards
cp "$final"/README.md README.md
git add -A
commit "Tomas Novak" tomas.novak@fernhill.example 2026-06-15T09:12:00Z "Dashboards: jobqueue 2.0 metric names (queues are sharded now)"

cp "$final"/rules.toml alerts/rules.toml
git add -A
commit "Lena Ortiz" lena.ortiz@fernhill.example 2026-08-11T11:47:00Z "Alert when the API's TLS certificate is about to expire"
rm -rf "$final"
test -z "$(git status --porcelain)"

python3 /task-setup/make_metrics.py data
