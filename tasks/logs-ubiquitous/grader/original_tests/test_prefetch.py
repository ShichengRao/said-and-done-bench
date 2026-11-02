import threading
from datetime import date

import pytest

from exporter.feed import COLUMNS, FeedFile
from exporter.prefetch import FeedTimeout, Prefetcher

DAY = date(2026, 6, 2)


def feed_of(tmp_path, count, other_days=0):
    path = tmp_path / "feed.csv"
    lines = [",".join(COLUMNS)]
    for n in range(count):
        lines.append(f"{1000 + 2 * n},r-{n:04x},FH-260602-{n + 1:04d},2026-06-02,C-{20000 + n},{10 + n}.00,USD")
    for n in range(other_days):
        lines.append(f"{1001 + 2 * n},r-x{n:03x},FH-260601-{n + 1:04d},2026-06-01,C-{30000 + n},5.00,USD")
    path.write_text("\n".join(lines) + "\n")
    return FeedFile(path)


def test_reads_the_day_in_pages(tmp_path):
    feed = Prefetcher(feed_of(tmp_path, 7, other_days=3), DAY, page_size=3, page_timeout=5).start()
    rows = feed.rows()
    assert [row.invoice_no for row in rows] == [f"FH-260602-{n:04d}" for n in range(1, 8)]
    assert feed.pages == 3


def test_a_day_that_fits_in_one_page(tmp_path):
    feed = Prefetcher(feed_of(tmp_path, 4), DAY, page_size=100, page_timeout=5).start()
    assert len(feed.rows()) == 4 and feed.pages == 1


def test_gives_up_when_the_feed_stops(tmp_path):
    class Stalled:
        def __init__(self, feed):
            self.feed = feed
            self.release = threading.Event()

        def fetch_page(self, invoice_date, after=0, limit=100):
            self.release.wait()
            return self.feed.fetch_page(invoice_date, after, limit)

    conn = Stalled(feed_of(tmp_path, 2))
    feed = Prefetcher(conn, DAY, page_size=100, page_timeout=0.2).start()
    with pytest.raises(FeedTimeout) as raised:
        feed.rows()
    conn.release.set()
    assert raised.value.rows == 0
    assert "no rows from the feed for 0.2s" in str(raised.value)
