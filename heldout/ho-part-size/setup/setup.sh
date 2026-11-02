#!/usr/bin/env bash
# Builds the repository's history: shipper with per-environment config, then
# production's bigger parts (OPS-377).
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

cd /workspace
git init -q -b main
cp config/production.toml /tmp/production.toml
grep -v -e '^chunk' -e 'Bigger parts' /tmp/production.toml > config/production.toml
git add -A
commit "Rui Almeida" rui@example.com 2026-06-02T11:00:00Z "shipper: multipart uploads to the store, with per-environment config"
cp /tmp/production.toml config/production.toml
git add config/production.toml
commit "Dana Whitfield" dana@example.com 2026-08-18T15:40:00Z "Production: 16 MiB parts for the big installers (OPS-377)"
