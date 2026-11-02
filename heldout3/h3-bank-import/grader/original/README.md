# ledgerly

The studio's books: every transaction on every account, one per line in
`data/ledger.jsonl` (`LEDGERLY_DATA` names another folder), each a JSON
object with `date`, `amount` (a string, `"-12.50"`; money out is negative),
`description`, `account`, and `category`. `data/rules.toml` says which
descriptions get which category.

    python3 -m ledgerly add 2026-10-03 -12.50 "Coffee beans" --account business
    python3 -m ledgerly list --account business --month 2026-10
    python3 -m ledgerly summary --month 2026-10

Accounts: `business` (Nordbank) and `card` (the Westpay card).

To try something without touching the real books, point `LEDGERLY_DATA` at
a scratch folder (copy `data/rules.toml` into it for the categories).

## Tests

    python3 -m pytest
