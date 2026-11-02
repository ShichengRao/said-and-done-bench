# Northgate import format

Northgate Accounting imports one file per business day,
`ledger-YYYY-MM-DD.csv`, into its inbound folder. It's comma-separated
with a header row:

```
invoice_no,invoice_date,customer_id,amount,currency
FH-260602-0001,2026-06-02,C-20417,1240.00,USD
```

One row per invoice, two decimals in `amount`. Northgate rejects a file with
the same `invoice_no` twice, and its month-end close compares the files'
totals with ours, so a file has to contain every invoice of the day exactly
once.
