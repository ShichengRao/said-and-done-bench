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
        # A redelivered row comes with a new feed_seq and row_id, but its
        # invoice_no is the invoice's own and never reused. Two invoices can
        # share a customer, date, and total (a standing order placed twice),
        # so those can't identify a redelivery.
        original = first_seen.get(row.invoice_no)
        if original is not None:
            log.warning("dropped %s (feed_seq %d) as a redelivery of feed_seq %d", row.invoice_no, row.feed_seq, original.feed_seq)
            continue
        first_seen[row.invoice_no] = row
        kept.append(row)
    log.info("checked %d rows, %d redelivered", len(rows), len(rows) - len(kept))
    return kept
