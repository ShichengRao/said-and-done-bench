"""Reading a day's rows from the feed in pages, on a background thread.

The replica cancels any query that runs past its statement timeout, and on
busy days the one query for the whole day came close, so the export reads
the day in pages of `page_size` rows, in feed_seq order. A thread fetches
the pages while the job takes the ones already fetched; if no page arrives
for `page_timeout` seconds, the job gives up (exit 3, which exp-worker
retries once).
"""

import logging
import queue
import threading

log = logging.getLogger(__name__)


class FeedTimeout(Exception):
    """No page came from the feed in time."""

    def __init__(self, message, rows):
        super().__init__(message)
        self.rows = rows


class Prefetcher:
    def __init__(self, conn, export_date, page_size=100, page_timeout=600.0):
        self.conn = conn
        self.export_date = export_date
        self.page_size = page_size
        self.page_timeout = page_timeout
        self.pages = 0
        self._pages = queue.Queue(maxsize=4)
        self._thread = threading.Thread(target=self._fetch, name="feed-prefetch", daemon=True)

    def start(self):
        self._thread.start()
        return self

    def _fetch(self):
        after = 0
        while True:
            page = self.conn.fetch_page(self.export_date, after=after, limit=self.page_size)
            log.debug("page of %d rows: feed_seq %d..%d", len(page), page[0].feed_seq, page[-1].feed_seq)
            self._pages.put(page)
            if len(page) < self.page_size:
                self._pages.put(None)  # That was the day's last page.
                return
            after = page[-1].feed_seq

    def rows(self):
        """Every row of the day, in feed order, as the pages come in."""
        rows = []
        while True:
            try:
                page = self._pages.get(timeout=self.page_timeout)
            except queue.Empty:
                raise FeedTimeout(f"no rows from the feed for {self.page_timeout:g}s (after {len(rows)} rows)", len(rows)) from None
            if page is None:
                return rows
            self.pages += 1
            rows.extend(page)
