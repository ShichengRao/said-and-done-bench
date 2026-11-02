#!/usr/bin/env bash
# Builds the repository's history: the calculator, the formulary's new entry, then today's EHR extract.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
mv formulary/nevarocin.md /tmp/nevarocin.md
git init -q -b main
git add -A -- . ':!data' ':!orders'
commit "Priya Natarajan" priya.natarajan@stbrigid-pharmacy.example 2026-02-17T15:10:00+00:00 "pharmcalc: tamberin and corvalex"
cp /tmp/nevarocin.md formulary/nevarocin.md
git add formulary/nevarocin.md
commit "Priya Natarajan" priya.natarajan@stbrigid-pharmacy.example 2026-10-15T09:30:00+01:00 "formulary: nevarocin (D&TC, 14 October)"
git add -A
commit "ehr-extract" ehr@stbrigid-pharmacy.example 2026-10-26T16:30:00+00:00 "data: EHR extract"
test -z "$(git status --porcelain)"
