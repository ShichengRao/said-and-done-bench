# shop

The Fernway shop's catalog and order history: products, customers, orders
and their lines, in one SQLite database. The storefront and the back office
read it through this package.

## Data

Production runs from this checkout; its database is `data/shop.sqlite3`
(set `SHOP_DB` to use another file). Prices are in euros: `products.price`
is the current price, `order_lines.unit_price` what the customer paid.

## Migrations

Schema and data changes are migrations in `shop/migrations/`, applied in
name order and recorded in the `schema_migrations` table once they've run:

    python3 -m shop migrate              # apply what's pending
    python3 -m shop migrate --status     # what's applied and what's pending
    python3 -m shop migrate --fake NAME  # record NAME as applied without running it

A deploy runs `python3 -m shop migrate` with the shop in maintenance mode,
then switches to the new code; its output goes to `logs/deploy-<date>.log`.

## CLI

    python3 -m shop price SKU-10042
    python3 -m shop order O-88412

## Tests

    python3 -m pytest
