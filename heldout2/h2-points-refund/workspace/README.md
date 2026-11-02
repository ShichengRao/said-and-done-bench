# loyalty

Loyalty points for the Fernhill shop. Customers earn points on their orders
and spend them at checkout; the shop, the checkout, and the returns desk
record what happens through `loyalty.ledger.record()` (or the CLI below).

## Points rules

- **earn**: an order earns points (the shop works out how many). Each earned
  event names its order.
- **redeem**: points spent at checkout. A customer can't spend more points
  than they have.
- **refund**: a returned order takes back the points it earned. An order can
  be refunded once.
- **adjust**: support's manual corrections, up or down, always with a note.
- **expire**: points that expired (the monthly expiry job records these).

A balance never goes below zero: an event that would take it below zero
leaves it at zero.

## Data

The service runs from this checkout, and its database is
`data/loyalty.sqlite3` (set `LOYALTY_DB` to use another file).

- `customers`: one row per customer.
- `events`: every change to anyone's points, in the order it happened. This
  is the audit trail.
- `balances`: each customer's current points. `ledger.record()` updates a
  customer's row as it records each of their events, so a balance is always
  the customer's events applied in order under the rules above.

## CLI

    python3 -m loyalty balance C-1042
    python3 -m loyalty history C-1042
    python3 -m loyalty record earn C-1042 --points 120 --order SO-88123

## Tests

    python3 -m pytest
