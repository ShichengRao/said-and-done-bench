# Meter billing adjustment service

Larkspur Water Cooperative (fictional) bills member accounts from cumulative
meter readings. Meter corrections often arrive after invoices were issued, and
several meters, accounts and invoice periods share one progressive pricing pool,
so a late correction can change the amounts on other invoices. This service
ingests reading deliveries incrementally, recomputes the current invoice lines
and issues signed adjustments against what was previously billed. Historical
postings are never rewritten.

Run from this directory:

```
python -m meter_billing replay --history data/customer_history.json --store output/billing.db --output output/adjustments.json
python -m pytest
```

## Layout

* `meter_billing/service.py` – the durable service API: `initialize(path, config)`,
  `close(path, command)` and `snapshot(path)` on a standard-library SQLite store.
  This is still a prototype: it does not retain deliveries, reconstruct usage or
  price anything yet.
* `meter_billing/pricing.py` – progressive tier pricing helper.
* `meter_billing/cli.py` – the `replay` command used by operations.
* `docs/billing_rules.md` – the billing contract the service must implement.
* `data/customer_history.json` – the customer's seed configuration (`config`) and
  its sequence of close commands (`commands`), in order.

Change code and add tests as needed; helper modules and test restructuring are
fine. `README.md`, `docs/`, `data/` and `pytest.ini` are customer and operational
records and must remain unchanged. Everything is fictional and offline; no
network or wall-clock time is used.

## The replay command

`replay` initializes the store at `--store` with the history's `config` (repeating
with the same config is a no-op), sends every command to `close` in order, then
writes the adjustment run to `--output`:

```
{"customer": "<customer>",
 "closes": [<close response>, ...],      # one per command, in command order
 "targets": [<current invoice line>, ...],
 "clock": <store clock>,
 "delivery_count": <distinct deliveries retained>}
```

`closes` are the responses returned by `close` and `targets`, `clock` and
`delivery_count` come from `snapshot` after the last command. Because operation
IDs are bound to their commands, rerunning the same history against the same store
returns the original responses and bills nothing twice. The output is written
atomically; if any command is rejected the command exits nonzero, explains on
stderr and leaves an existing output file untouched (accepted closes before the
rejected one stay committed in the store, as the contract requires).

`output/adjustments.json` for the attached customer history is the artifact
billing operations will post from.
