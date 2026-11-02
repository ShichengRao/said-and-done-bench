# invoicing

Due dates and printable invoices for what billing issues. Billing exports
every invoice nightly to `data/invoices.json` (set `INVOICING_DATA` to read
another file); timestamps in the export are UTC.

- `invoicing/terms.py`: payment terms (NET30, EOM, EOM+15, ...).
- `invoicing/due.py`: an invoice's due date.
- `invoicing/render.py`: the text the PDF service lays out.

## CLI

    python3 -m invoicing due INV-20417
    python3 -m invoicing show INV-20417

## Tests

    python3 -m pytest
