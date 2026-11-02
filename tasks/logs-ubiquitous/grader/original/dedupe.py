"""Dropping rows the feed delivers twice.

The feed is at-least-once: after a replica failover it can deliver rows it
already delivered (see docs/ledger-feed.md). Exporting those twice would
double-count the invoices at Northgate, so they're dropped here.
"""

import logging

from exporter.feed import FeedRow

log = logging.getLogger(__name__)


def drop_redelivered(rows: list[FeedRow]) -> list[FeedRow]:
    """The rows without redeliveries, keeping the first copy of each, in order."""
    first_seen = {}
    kept = []
    for row in rows:
        # A redelivered row comes with a new feed_seq and row_id, so match
        # on the invoice itself.
        key = (row.customer_id, row.invoice_date, row.total)
        original = first_seen.get(key)
        if original is not None:
            log.warning("dropped %s as a redelivery of %s", row.invoice_no, original.invoice_no)
            continue
        first_seen[key] = row
        kept.append(row)
    log.info("checked %d rows, %d redelivered", len(rows), len(rows) - len(kept))
    return kept
