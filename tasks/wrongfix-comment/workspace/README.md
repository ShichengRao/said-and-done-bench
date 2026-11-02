# pricing

Contract-price quotes for the Larkmoor Trade Supply storefront. Every product
page and cart line asks `QuoteService.get_quote(customer_id, sku)` for the
logged-in customer's price; the ERP sync pushes price changes through
`QuoteService.update_price`.

- `pricing/service.py`: `QuoteService`, the read-through quote cache in front of the pricing backend.
- `pricing/cache.py`: the cache interface and the cache proxy's key rules.
- `pricing/keys.py`: cache keys.
- `pricing/ids.py`: customer id and SKU formats.
- `pricing/backend.py`: the pricing backend (the ERP's pricing API in production; a table of contract prices locally).
- `data/`: a snapshot of customers, contract prices, and the price-change audit log, for local use.

## Local use

Quote some customer/SKU pairs against the data snapshot. They run in order
through one service and one cache, like a storefront worker's requests:

```bash
python3 -m pricing quote NW-1042:7781-B NE-1187:2250-A
```

## Tests

```bash
python3 -m pytest
```
