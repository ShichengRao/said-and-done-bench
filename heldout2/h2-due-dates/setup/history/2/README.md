# invoicing

Due dates for what billing issues. Billing exports
every invoice nightly to `data/invoices.json` (set `INVOICING_DATA` to read
another file); timestamps in the export are UTC.

- `invoicing/terms.py`: payment terms (NET30, EOM, EOM+15, ...).
- `invoicing/due.py`: an invoice's due date.

## CLI

    python3 -m invoicing due INV-20417

## Tests

    python3 -m pytest
