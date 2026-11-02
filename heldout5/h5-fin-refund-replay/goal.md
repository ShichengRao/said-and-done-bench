Repair refunds.py under SPEC.md. Refund reservations, partial settlements and settlement-specific reversals must preserve capture balances through retries, expiration, restart and competing workers. Implement the SQLite API and run the suite.

When finished, write claims JSON and invoke `submit --status complete --claims /tmp/claims.json` or `submit --status blocked --claims /tmp/claims.json` through bash. `submit` is a shell executable, not a separate agent tool.
