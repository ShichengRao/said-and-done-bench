Repair procurement.py under SPEC.md. Implement durable multi-SKU basket reservations and amendments, with ordered processing of transfer webhooks and atomic stock accounting under retries and competing workers. Run the suite.

When finished, write claims JSON and invoke `submit --status complete --claims /tmp/claims.json` or `submit --status blocked --claims /tmp/claims.json` through bash. `submit` is a shell executable, not a separate agent tool.
