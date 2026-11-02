# nightly-export: when a run fails

From #finance-ops (Aug 27). exp-worker pages #finance-ops when a run fails;
these are the failures we see and what to do about them.

## "feed timed out: no rows from the feed for 600s"

The ledger replica can't keep up at 02:00, when every nightly job hits it at
once. Every one of these runs starts with the shared pool timing out ("failed
to acquire a connection from pool 'ledger-replica'"), and the replica's
slow-query warnings show it struggling on other nights too. exp-worker
retries the run 30 minutes later, once the other jobs are done; if the retry
also times out, rerun the export by hand after 08:00.

Longer term: a bigger exp-worker pool (DBA-412), and a longer `page_timeout`.

## "reconcile: exported total ... does not match ledger total ..."

Usually invoices posted to the ledger after the export read the feed. Rerun
the export after 09:00, once the ledger has closed the day; if it still
doesn't match, ask accounting.
