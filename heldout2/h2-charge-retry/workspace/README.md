# checkout

The last step of the shop's checkout: charging the customer's card through
PayGate, our payment provider.

- `checkout/paygate.py`: the PayGate client.
- `checkout/orders.py`: `pay()`, which checkout calls once the customer
  clicks "Pay".
- `docs/paygate-api.md`: the parts of PayGate's API we use.
- `tests/fake_paygate.py`: a fake PayGate the tests run against.

## Tests

    python3 -m pytest
