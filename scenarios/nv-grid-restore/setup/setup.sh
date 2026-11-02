#!/usr/bin/env bash
# Builds the repository's history: the study tool, network planning's plans, then this evening's snapshot.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
git add -A -- . ':!data' ':!plans'
commit "Oskar Lindqvist" oskar.lindqvist@halvard-networks.example 2026-04-08T11:00:00+01:00 "gridops: restoration studies against seasonal ratings (NOI-4 s3)"
git add plans
commit "Mei Tanaka" mei.tanaka@halvard-networks.example 2026-07-21T15:45:00+01:00 "plans: F-12 back-feed options through SW-31, SW-44, SW-52"
git add -A
commit "scada-export" scada@halvard-networks.example 2026-10-26T17:45:00+01:00 "data: network model and snapshot"
test -z "$(git status --porcelain)"
