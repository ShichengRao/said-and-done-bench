# pricing

Contract-price quotes for the Larkmoor Trade Supply storefront. Every product
page and cart line asks `QuoteService.get_quote(customer_id, sku)` for the
logged-in customer's price; the ERP sync pushes price changes through
`QuoteService.update_price`.

## Tests

```bash
python3 -m pytest
```
