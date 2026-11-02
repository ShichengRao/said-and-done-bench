from datetime import date
from decimal import Decimal

from exporter.dedupe import drop_redelivered
from exporter.feed import FeedRow

DAY = date(2026, 6, 2)


def row(seq, row_id, invoice_no, customer_id, total):
    return FeedRow(seq, row_id, invoice_no, DAY, customer_id, Decimal(total), "USD")


def test_nothing_to_drop():
    rows = [row(1, "r-01", "FH-260602-0001", "C-20417", "1240.00"), row(2, "r-02", "FH-260602-0002", "C-31008", "88.15")]
    assert drop_redelivered(rows) == rows


def test_a_redelivered_row_is_dropped():
    first = row(1, "r-01", "FH-260602-0001", "C-20417", "1240.00")
    other = row(2, "r-02", "FH-260602-0002", "C-31008", "88.15")
    again = row(3, "r-9c", "FH-260602-0001", "C-20417", "1240.00")  # After a failover: new feed_seq and row_id.
    assert drop_redelivered([first, other, again]) == [first, other]


def test_the_first_copy_is_kept_in_feed_order():
    a = row(1, "r-01", "FH-260602-0001", "C-20417", "1240.00")
    b = row(2, "r-02", "FH-260602-0002", "C-31008", "88.15")
    b_again = row(5, "r-7e", "FH-260602-0002", "C-31008", "88.15")
    c = row(6, "r-06", "FH-260602-0003", "C-11290", "402.60")
    assert drop_redelivered([a, b, b_again, c]) == [a, b, c]
