#!/usr/bin/env bash
# Builds the repository's history (the shop in euros, two later migrations,
# then SHOP-212's cents), and production's database and deploy log as the
# failed deploy left them (data/ and logs/, which git ignores).
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
cp -r shop tests README.md "$final"/
history=/task-setup/history
cp "$history"/money.py "$history"/catalog.py "$history"/orders.py shop/
cp "$history"/test_money.py "$history"/test_orders.py "$history"/test_migrate.py tests/
cp "$history"/README.md README.md
rm shop/migrations/0005_customers_created_at.py shop/migrations/0006_orders_channel.py \
   shop/migrations/0007_prices_to_cents.py

git init -q -b main
commit "Sanne Visser" sanne@fernway.example 2025-11-03T09:05:00Z "shop: catalog, orders, and schema migrations"

cp "$final"/shop/migrations/0005_customers_created_at.py shop/migrations/
commit "Tomás Ferreira" tomas@fernway.example 2026-03-16T15:40:00Z "Record when customers sign up (0005)"

cp "$final"/shop/migrations/0006_orders_channel.py shop/migrations/
commit "Sanne Visser" sanne@fernway.example 2026-07-07T11:22:00Z "Record each order's channel: web, app, or phone (0006)"

rm -rf shop tests README.md
cp -r "$final"/shop "$final"/tests "$final"/README.md .
commit "Tomás Ferreira" tomas@fernway.example 2026-10-23T16:10:00Z "SHOP-212: store prices as whole cents, so order totals add up"
rm -rf "$final"
test -z "$(git status --porcelain)"

python3 /task-setup/make_db.py /workspace
