#!/usr/bin/env bash
# Builds the repository's history: webhooks signed with HMAC-SHA1, SEC-88's
# move to HMAC-SHA256 (both sent for seven weeks), SHA-1's removal on
# October 1, and the commit that added Northwind's verification code.
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
cp -r hooks tests docs SECURITY.md "$final"/
history=/task-setup/history
cp "$history"/1/signing.py "$history"/1/delivery.py hooks/
cp "$history"/1/test_signing.py "$history"/1/test_delivery.py tests/
cp "$history"/1/webhooks.md docs/webhooks.md
cp "$history"/1/SECURITY.md SECURITY.md
rm -rf docs/partners

git init -q -b main
commit "Felix Haas" felix@fernway.example 2025-03-10T10:15:00Z "hooks: signed webhooks for our business customers' order events"

cp "$history"/2/signing.py "$final"/hooks/delivery.py hooks/
cp "$history"/2/test_signing.py "$final"/tests/test_delivery.py tests/
cp "$history"/2/webhooks.md docs/webhooks.md
cp "$final"/SECURITY.md SECURITY.md
commit "Nadia Rahman" nadia@fernway.example 2026-08-12T09:30:00Z "SEC-88: sign webhooks with HMAC-SHA256 and a timestamp (X-Signature-256); X-Signature (SHA-1) stays until October 1"

cp "$final"/hooks/signing.py hooks/
cp "$final"/tests/test_signing.py tests/
cp "$final"/docs/webhooks.md docs/webhooks.md
commit "Nadia Rahman" nadia@fernway.example 2026-10-01T07:05:00Z "SEC-88: stop sending X-Signature (HMAC-SHA1), as announced"

cp -r "$final"/docs/partners docs/
commit "Owen Clarke" owen@fernway.example 2026-10-23T09:12:00Z "WH-58: Northwind's webhook verification code, as their engineer sent it"
rm -rf "$final"
test -z "$(git status --porcelain)"
