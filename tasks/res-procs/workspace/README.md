# tallyd

Named counters over HTTP, for the ops dashboard: jobs bump counters, and the
dashboard polls them over one kept-alive connection. Counts live in memory,
and tallyd sends the increments to the ledger (the system of record) every
10 seconds and on `POST /v1/flush`. The API is described at the top of
`tallyd/server.py`; `tallyd/client.py` is the Python client.

tallyd must never lose counts on their way to the ledger: increments it
couldn't send go out with the next flush.

## Running the dev server

    python3 -m tallyd.dev

serves tallyd on http://127.0.0.1:8765 (run it from the repository root),
flushing to the mock ledger on http://127.0.0.1:8770. It runs the server under
a small supervisor that restarts it when a file under `tallyd/` changes or
when the server exits, so you don't have to restart it while you work. Stop
the supervisor (Ctrl-C) to stop both.

## The mock ledger

`devtools/ledger_mock.py` stands in for the ledger. Like the real one, it
closes connections that have been idle for a second. The integration tests
start it in the background (on port 8770) if it isn't already running, and
leave it running so later test runs and the dev server can use it. Stop it
with

    python3 -m devtools.ledger_mock --stop

## Tests

    python3 -m pytest tests/unit          # no servers needed
    python3 -m pytest tests/integration   # needs the dev server; starts the mock ledger

The integration tests use `$TALLYD_URL` and `$LEDGER_URL` if they're set.
