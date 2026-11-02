# gateway

The ingest gateway takes messages from producers, buffers them, and forwards
them to the store with a pool of drain workers. Its settings live in
`config/gateway.toml`; `gateway/` is the gateway's buffering and draining
logic, which we run against captured traffic to size it.

## How it loses messages

When every drain worker is busy and the buffer is full, an arriving message
is lost. The gateway doesn't count these (that's how the 2026-10-14 loss went
unnoticed until the store came up short). Loss is measured from the egress
capture instead: producers number their messages, and `gateway/analysis.py`
counts the gaps.

## The egress capture

Every batch a drain worker forwards is compressed and appended to the egress
capture before the worker takes its next batch, so capturing is part of the
drain's cost: the worker pays `capture.ms_per_kib` for every KiB the capture
actually writes. How many bytes that is depends on what's in the batch and on
what came before it in the capture's compressed stream (bulk jobs' records
compress far better than the services' traffic), which is why replays run
the real capture writer instead of estimating it.

## Replaying traffic

`traffic/` holds summaries of production traffic: per 100 ms, how many
messages arrived, their mean size, and the producer that sent most of them.
To see how a configuration would have handled one:

    python3 tools/replay.py traffic/2026-10-14-evening.csv
    python3 tools/replay.py traffic/2026-10-14-evening.csv --slots 128

`--slots` overrides `buffer_slots` from the config for one replay. A replay
runs the gateway on the traffic with the real capture writer, which writes
the egress capture to a new directory under `/scratch/replay/`, then runs the
standard analyzer on it (`tools/analyze.py`, the same one we run on
production captures). Captures are kept so you can re-analyze or dig into
them later; nothing deletes them.

## Tests

    python3 -m pytest
