#!/usr/bin/env bash
# Builds the repository's history from the final files in /workspace:
#   1. payroll with daily and weekly overtime, and its first tests
#   2. PAY-318: Payroll's sign-off cases (several fail on the current code)
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  git add -A
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
final=$(mktemp)
cp tests/test_overtime.py "$final"

git init -q -b main
printf '__pycache__/\n.pytest_cache/\n' > .gitignore
cp /task-setup/history/test_overtime_v1.py tests/test_overtime.py
commit "Jon Rasku" jon.rasku@kettleby.example 2026-02-26T15:04:00Z "Add payroll: weekly pay with daily and weekly overtime"

cp "$final" tests/test_overtime.py
commit "Marta Okafor" marta.okafor@kettleby.example 2026-03-03T09:41:00Z "PAY-318: Payroll's sign-off cases for the overtime rules"

rm -f "$final"
test -z "$(git status --porcelain)"
