# The ledger's invoice feed

The ledger publishes every posted invoice to its feed, which the replica
serves to downstream jobs. One row per invoice:

| Column | Meaning |
| --- | --- |
| `feed_seq` | Position in the feed. Increases with every row the feed sends, including redeliveries. |
| `row_id` | The replica's id for the stored row. Reissued when the replica rebuilds after a failover. |
| `invoice_no` | The invoice number, `FH-YYMMDD-NNNN`, assigned by the ledger when the invoice is posted. Printed on the invoice; never reused. |
| `invoice_date` | The business day the invoice belongs to (America/Chicago). |
| `customer_id` | The billed account, `C-NNNNN`. |
| `total` | Invoice total, two decimals. |
| `currency` | ISO 4217 code. Always `USD` today. |

## Delivery

The feed is at-least-once. After a replica failover, the replica replays
recent rows to consumers that may have missed them, so a consumer can see a
row it already has. A redelivered row has a new `feed_seq` and a new
`row_id`; its other columns are the same as the first delivery's.

Failovers are rare (this year: February 14, March 28, June 17, August 11,
and September 2), but anything that totals the feed has to cope with them.

## Daily totals

The ledger's own total for a business day (the sum of `total` over that
day's invoices, each counted once) comes from the ledger's reporting API.
The nightly export reconciles against it.
