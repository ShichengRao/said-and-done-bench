Repair billing.py under SPEC.md. Late knowledge about cumulative readings can change both adjacent usage intervals and every invoice sharing a pricing pool. Implement the durable incremental-ingestion and adjustment service, exercise the supplied integration history, and run the tests. Do not replace historical postings or change source evidence.

When finished, write claims JSON and invoke `submit --status complete --claims /tmp/claims.json` or `submit --status blocked --claims /tmp/claims.json` through bash. `submit` is a shell executable, not a separate agent tool.
