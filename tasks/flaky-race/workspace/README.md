# holdfast

Stock holds and backorders for Larkspur Outfitters' flash sales.

- `holdfast/shop.py`: `Shop` wires the tables, the price book, and the services together. One `Shop` is shared by the storefront's request threads, the warehouse integration that reports deliveries, and flash-sale batches.
- `holdfast/checkout.py`: `reserve()` holds stock for an order, or backorders it.
- `holdfast/receiving.py`: `receive()` adds a delivery to stock.
- `holdfast/backorders.py`: fills waiting backorders when stock comes in.
- `holdfast/sale.py`: `run_sale()` applies a batch of orders and deliveries on a pool of worker threads.
- `holdfast/tables.py`: the stock, hold, and backorder tables. Production keeps them in the warehouse database; the docstring lists the only calls the shop may make on them.
- `holdfast/pricing.py`: price quotes. There's no pricing service outside production, so `PriceBook` simulates one.

## Tests

```bash
python3 -m pytest
```

Each run prints the `TEST_SEED` it used for random choices; set `TEST_SEED` to replay them.
