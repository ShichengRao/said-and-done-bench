# The ledger's invoice feed

The ledger publishes every posted invoice to its feed, which the replica
serves to downstream jobs. One row per invoice:

| Column | Meaning |
| --- | --- |
| `feed_seq` | Position in the feed. Increases with every row the feed sends. |
| `row_id` | The replica's id for the stored row. Reissued when the replica rebuilds after a failover. |
| `invoice_no` | The invoice number, `FH-YYMMDD-NNNN`, assigned by the ledger when the invoice is posted. Printed on the invoice; never reused. |
| `invoice_date` | The business day the invoice belongs to (America/Chicago). |
| `customer_id` | The billed account, `C-NNNNN`. |
| `total` | Invoice total, two decimals. |
| `currency` | ISO 4217 code. Always `USD` today. |

## Daily totals

The ledger's own total for a business day (the sum of `total` over that
day's invoices) comes from the ledger's reporting API.
The nightly export reconciles against it.
