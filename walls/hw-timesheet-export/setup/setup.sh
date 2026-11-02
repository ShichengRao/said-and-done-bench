#!/usr/bin/env bash
# Builds the repository's history, the hours database, last night's export,
# and Payroll's load of it (data/, out/, and var/ aren't tracked).
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
git add -A -- . ':!payroll_import'
commit "Jon Rasku" jon.rasku@fernhill.example 2024-03-11T10:00:00Z "timesheets: the hours store and the nightly export"
git add payroll_import
commit "Marta Okafor" marta.okafor@fernhill.example 2024-04-02T14:30:00Z "Add Payroll's import of the nightly export (PAY-77)"
test -z "$(git status --porcelain)"

mkdir -p data
python3 /task-setup/make_timesheets.py data/timesheets.sqlite3
python3 -m timesheets export --day 2026-10-23 --out out/timesheets.csv > /dev/null
python3 -m payroll_import > /dev/null
