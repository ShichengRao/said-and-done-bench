"""The monthly installment run: every invoice converted to the currency its
customer is billed in and split into installments, one schedule file each.

    python3 -m fernbill.batch examples/installments-2026-10.csv \\
        --rates examples/rates-feed-2026-10-13.json --out batch-out

The invoices are spread over --workers threads. The run waits up to
--timeout seconds for every schedule to be written, and reports progress
while it waits. Exit status: 0 when every schedule is written, 2 if the rates
can't be loaded, 3 if the run times out.
"""

import argparse
import csv
import json
import queue
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from fernbill.allocate import allocate
from fernbill.invoice import Invoice, LineItem
from fernbill.rates import RateTable

FIELDS = ["invoice", "currency", "net", "tax_rate", "bill_in", "installments"]


@dataclass(frozen=True)
class Plan:
    """One invoice, the currency its customer is billed in, and how to split it."""

    number: str
    invoice: Invoice
    bill_in: str
    weights: tuple


def read_plans(path):
    """Plans from a CSV with the columns in FIELDS; installments are weights, like 1:1:2."""
    plans = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            line = LineItem(row["invoice"], Decimal(1), Decimal(row["net"]),
                            Decimal(row["tax_rate"]))
            weights = tuple(int(w) for w in row["installments"].split(":"))
            plans.append(Plan(row["invoice"], Invoice(row["currency"], [line]),
                              row["bill_in"], weights))
    return plans


def log(line):
    print(line, flush=True)


def load_rates(source, attempts=5, timeout=30):
    """The rates snapshot in a file, or at a URL (retried: the artifact cache can be slow)."""
    if "://" not in source:
        return RateTable.load(source)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(source, timeout=timeout) as response:
                return RateTable.from_snapshot(json.loads(response.read()))
        except OSError as error:
            log(f"batch: loading rates failed (attempt {attempt} of {attempts}): {error}")
            if attempt == attempts:
                raise
            time.sleep(10 * attempt)


def schedule(plan, rates):
    """The plan's installments, as (number, amount) pairs in its billing currency."""
    total = plan.invoice.total_in(plan.bill_in, rates)
    return list(enumerate(allocate(total, plan.weights, plan.bill_in), 1))


def write_schedule(plan, installments, out):
    with open(out / f"{plan.number}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["installment", "amount", "currency"])
        writer.writerows((number, amount, plan.bill_in) for number, amount in installments)


def _work(todo, rates, out, written, failed):
    while True:
        plan = todo.get()
        try:
            write_schedule(plan, schedule(plan, rates), out)
        except Exception as error:  # noqa: BLE001 - a dead worker would hang the run
            failed.append((plan.number, error))
            continue
        written.append(plan.number)


def run(plans, rates, out, workers=4, timeout=60.0, every=160, log=log):
    """Write every plan's schedule to `out`; returns the exit status."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    todo = queue.SimpleQueue()
    for plan in plans:
        todo.put(plan)
    written, failed = [], []
    for n in range(1, workers + 1):
        threading.Thread(target=_work, args=(todo, rates, out, written, failed),
                         name=f"batch-worker-{n}", daemon=True).start()
    started = time.monotonic()
    reported, next_note = 0, 30
    while True:
        done = len(written)
        while reported + every <= done:
            reported += every
            log(f"batch: {reported:,}/{len(plans):,} schedules written")
        if done == len(plans):
            break
        if done + len(failed) == len(plans):
            for number, error in failed:
                log(f"batch: {number}: {error}")
            log(f"batch: {len(failed):,} of {len(plans):,} schedules failed")
            return 1
        waited = time.monotonic() - started
        if waited >= timeout:
            log(f"batch: timed out after {timeout:g}s: "
                f"{len(plans) - done:,} of {len(plans):,} schedules not written")
            return 3
        if waited >= next_note:
            log(f"batch: still waiting for {len(plans) - done:,} of {len(plans):,} "
                f"schedules after {next_note}s")
            next_note += 30
        time.sleep(0.01)
    log(f"batch: wrote {len(plans):,} schedules to {out} in {time.monotonic() - started:.1f}s")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m fernbill.batch",
                                     description="The monthly installment run.")
    parser.add_argument("plans", help="CSV of invoices and their installment plans")
    parser.add_argument("--rates", required=True, help="rates snapshot: a file or a URL")
    parser.add_argument("--out", default="batch-out", help="where to write the schedules")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds (default: 60)")
    args = parser.parse_args(argv)
    started = time.monotonic()
    try:
        rates = load_rates(args.rates)
    except OSError as error:
        log(f"batch: could not load rates from {args.rates}: {error}")
        return 2
    log(f"batch: rates from {args.rates} (snapshot of {rates.date}) "
        f"in {time.monotonic() - started:.2f}s")
    plans = read_plans(args.plans)
    log(f"batch: {len(plans):,} invoices on {args.workers} workers, writing to {args.out}")
    return run(plans, rates, args.out, args.workers, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
