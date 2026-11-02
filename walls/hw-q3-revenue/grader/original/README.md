# revenue

Quarterly revenue for Fernhill GmbH's board pack, from the ERP's nightly
export of invoices and credit notes (`data/invoices.csv`,
`data/credit_notes.csv`; set `REVENUE_DATA` to read another folder).

`docs/revenue-rules.md` says what counts. `audit/` holds the external
auditors' working papers, for reconciling against.

    python3 -m revenue report 2026Q3     # the quarter's revenue
    python3 -m revenue lines 2026Q3      # the documents behind it, as CSV

## Tests

    python3 -m pytest
