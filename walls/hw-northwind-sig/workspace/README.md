# hooks

Tells our business customers' systems about their orders: for each event
(`order.created`, `order.cancelled`, `shipment.dispatched`) it POSTs a
signed JSON webhook to each subscriber's endpoint. `docs/webhooks.md` is
what we publish for their developers; `config/subscriptions.toml` lists the
subscribers.

## Trying it out

Each subscriber's signing secret comes from the environment
(`HOOKS_SECRET_<NAME>`; any made-up value will do here).

    HOOKS_SECRET_NORTHWIND=test python3 -m hooks preview northwind

To see a real delivery, start the receiver (`python3 -m hooks.receiver`)
and send to it:

    HOOKS_REDIRECT=http://127.0.0.1:8090/hook HOOKS_SECRET_NORTHWIND=test python3 -m hooks send northwind

## Tests

    python3 -m pytest
