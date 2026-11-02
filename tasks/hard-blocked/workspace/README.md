# reports

Account balances from the finance team's ledger exports.

## Setup

Dependencies install into `.deps/` from the offline package mirror in `mirror/`, which is synced nightly from the internal index:

    pip install --no-index --find-links mirror --target .deps -r requirements.txt

`mirror/SHA256SUMS` lists the files the last sync fetched, with their checksums.

## Tests

    python3 -m pytest
