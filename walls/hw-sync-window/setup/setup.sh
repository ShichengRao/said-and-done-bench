#!/usr/bin/env bash
# Builds the repository's history: the sync when the SKU list was small,
# then two updates of the list as the range grew to 9,600 products.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() {  # commit NAME EMAIL DATE MESSAGE
  git add -A
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
    git commit -q -m "$4"
}

# The SKU list as it was: the first N products of today's list, in the order they were added.
skus_as_of() {  # skus_as_of COUNT DATE
  python3 - "$1" "$2" <<'PY'
import random, sys
count, date = int(sys.argv[1]), sys.argv[2]
lines = open('/tmp/skus.final').read().splitlines()
skus = lines[1:]
order = list(skus)
random.Random('cat-history').shuffle(order)
kept = sorted(order[:count])
open('data/skus.txt', 'w').write(f'# Every product we sell from Halden Wholesale (exported from the PIM, {date}).\n'
                                 + ''.join(sku + '\n' for sku in kept))
PY
}

cd /workspace
cp data/skus.txt /tmp/skus.final
skus_as_of 3800 2025-09-12
git init -q -b main
commit "Arjun Mehta" arjun@fernway.example 2025-09-15T11:00:00Z "catalog_sync: nightly prices and stock from Halden Wholesale"

skus_as_of 6400 2026-08-28
commit "Lotte Jansen" lotte@fernway.example 2026-09-01T09:20:00Z "SKU list: Halden's autumn range (6,400 products)"

cp /tmp/skus.final data/skus.txt
commit "Lotte Jansen" lotte@fernway.example 2026-10-21T14:45:00Z "SKU list: Halden's winter range and the kitchen line (9,600 products)"
test -z "$(git status --porcelain)"
