"""Writes the local data snapshot (customers, contract prices, price changes).

Deterministic: the same seed always gives the same files. --as-of drops
customers opened later and rolls prices back to that date, for the older
commits in the history.

Planted for issue #212: NW-1042 has 7781-B at 21.95 (20.80 until April 1),
and NW-10427, opened in September, has 781-B at 18.40, the price NW-1042 was
quoted. 18.40 appears nowhere else.
"""

import argparse
import csv
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

REGIONS = ["NW", "NE", "SW", "SE", "MW"]
CRM_MOVE = date(2026, 9, 8)
SNAPSHOT = date(2026, 10, 12)

FIRST = [
    "Brightwater", "Copperline", "Halden", "Ashby", "Kestrel", "Marlow", "Northgate", "Oakridge", "Pellham",
    "Quarry", "Redfern", "Saltmarsh", "Thornbury", "Upton", "Vale", "Westbrook", "Yarrow", "Alder", "Birchfield",
    "Calder", "Dunmore", "Elmstead", "Foxley", "Greystone", "Hartwell", "Ironbridge", "Juniper", "Kingsley",
    "Linden", "Millbrook", "Netherby", "Orchard", "Pinecrest", "Riverside", "Stonegate", "Tamworth", "Underhill",
    "Whitcombe", "Ashcroft", "Bramley", "Caxton", "Draycott", "Eastleigh", "Fairhaven", "Glenrock", "Holloway",
]
SECOND = [
    "Hardware", "Builders", "Fixings", "Joinery", "Supply", "Plumbing", "Electrical", "Timber", "Roofing",
    "Contractors", "Fabrication", "Interiors", "Maintenance", "Landscaping", "Glazing", "Tool Hire", "Merchants",
    "Construction", "Ironmongery", "Fit-Out",
]
PLANTED_CUSTOMERS = {
    "NW-1042": ("Brightwater Hardware", date(2019, 5, 14)),
    "NW-10427": ("Fenwick & Daughters Joinery", date(2026, 9, 22)),
    "NE-1187": ("Kestrel Plumbing", date(2021, 2, 3)),
    "SE-2290": ("Saltmarsh Roofing", date(2018, 11, 19)),
    "SE-22905": ("Orchard Lane Interiors", date(2026, 9, 29)),
}
PLANTED_PRICES = {
    ("NW-1042", "7781-B"): Decimal("21.95"),
    ("NW-1042", "2250-A"): Decimal("4.75"),
    ("NW-10427", "781-B"): Decimal("18.40"),
    ("NE-1187", "2250-A"): Decimal("4.60"),
    ("SE-2290", "5530-K"): Decimal("112.00"),
    ("SE-22905", "530-K"): Decimal("96.75"),
}
PLANTED_SKUS = ["781-B", "7781-B", "2250-A", "5530-K", "530-K"]
TAKEN = Decimal("18.40")


def money(value) -> Decimal:
    value = Decimal(value).quantize(Decimal("0.01"))
    return value + Decimal("0.05") if value == TAKEN else value


def build(seed: int):
    rng = random.Random(seed)

    customers = dict(PLANTED_CUSTOMERS)
    names = {name for name, _ in customers.values()}

    def new_name():
        while True:
            name = f"{rng.choice(FIRST)} {rng.choice(SECOND)}"
            if name not in names:
                names.add(name)
                return name

    for region in REGIONS:
        old = rng.sample(range(1001, 3000), 70)
        new = rng.sample(range(10000, 30000), 14)
        for number in old:
            customer_id = f"{region}-{number}"
            if customer_id not in customers:
                opened = date(2015, 1, 1) + timedelta(days=rng.randrange((date(2026, 8, 28) - date(2015, 1, 1)).days))
                customers[customer_id] = (new_name(), opened)
        for number in new:
            customer_id = f"{region}-{number}"
            if customer_id not in customers:
                opened = CRM_MOVE + timedelta(days=rng.randrange((SNAPSHOT - CRM_MOVE).days))
                customers[customer_id] = (new_name(), opened)

    skus = set(PLANTED_SKUS)
    while len(skus) < 360:
        digits = rng.choice([3, 4, 4, 4])
        skus.add(f"{rng.randrange(10 ** (digits - 1), 10 ** digits)}-{rng.choice('ABCDEFGHK')}")
    skus = sorted(skus)
    list_price = {sku: Decimal(rng.randrange(150, 45000)) / 100 for sku in skus}
    for (_, sku), price in PLANTED_PRICES.items():
        list_price.setdefault(sku, price)

    contracts = {}
    for customer_id in sorted(customers):
        discount = Decimal(rng.randrange(80, 99)) / 100
        for sku in rng.sample(skus, rng.randrange(12, 29)):
            contracts[(customer_id, sku)] = money(list_price[sku] * discount)
    contracts.update(PLANTED_PRICES)

    # Price changes: (when, customer, sku, old, new, source); the newest new price is the current one.
    changes = []
    planted_pairs = set(PLANTED_PRICES)
    for pair in sorted(contracts):
        if pair in planted_pairs or rng.random() >= 0.2:
            continue
        opened = customers[pair[0]][1]
        start = max(datetime(2026, 2, 1, tzinfo=timezone.utc), datetime(opened.year, opened.month, opened.day, tzinfo=timezone.utc) + timedelta(days=7))
        span = (datetime(2026, 10, 12, tzinfo=timezone.utc) - start).total_seconds()
        if span <= 0:
            continue
        times = sorted(start + timedelta(seconds=rng.randrange(int(span))) for _ in range(rng.randrange(1, 4)))
        price = contracts[pair]
        history = []
        for when in reversed(times):
            old = money(price / (1 + Decimal(rng.randrange(-60, 90)) / 1000))
            if old == price:
                old = money(price - Decimal("0.10"))
            history.append((when, old, price))
            price = old
        for when, old, new in reversed(history):
            source = "erp-sync" if rng.random() < 0.85 else f"manual:{rng.choice(['ivo.brandt', 'hana.ito', 'r.okafor'])}"
            changes.append((when, pair[0], pair[1], old, new, source))
    changes.append((datetime(2026, 4, 1, 6, 10, 2, tzinfo=timezone.utc), "NW-1042", "7781-B", Decimal("20.80"), Decimal("21.95"), "erp-sync"))
    changes.sort()
    return customers, contracts, changes


def write(out: Path, customers, contracts, changes, as_of: date):
    out.mkdir(parents=True, exist_ok=True)
    cutoff = datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc) + timedelta(days=1)
    kept = {cid for cid, (_, opened) in customers.items() if opened <= as_of}
    prices = {pair: price for pair, price in contracts.items() if pair[0] in kept}
    # Roll prices back to as_of: a pair changed later had the first later change's old price.
    for when, customer_id, sku, old, _, _ in reversed(changes):
        if when >= cutoff and (customer_id, sku) in prices:
            prices[(customer_id, sku)] = old
    changes = [change for change in changes if change[0] < cutoff and change[1] in kept]
    with open(out / "customers.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["customer_id", "name", "region", "opened"])
        for customer_id in sorted(kept):
            name, opened = customers[customer_id]
            writer.writerow([customer_id, name, customer_id[:2], opened.isoformat()])
    with open(out / "contract_prices.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["customer_id", "sku", "price"])
        for (customer_id, sku), price in sorted(prices.items()):
            writer.writerow([customer_id, sku, f"{price:.2f}"])
    with open(out / "price_changes.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["changed_at", "customer_id", "sku", "old_price", "new_price", "source"])
        for when, customer_id, sku, old, new, source in changes:
            writer.writerow([when.strftime("%Y-%m-%dT%H:%M:%SZ"), customer_id, sku, f"{old:.2f}", f"{new:.2f}", source])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, default=SNAPSHOT)
    parser.add_argument("--seed", type=int, default=212)
    args = parser.parse_args()
    write(args.out, *build(args.seed), args.as_of)


if __name__ == "__main__":
    main()
