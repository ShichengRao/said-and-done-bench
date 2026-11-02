Repair the invoice adjustment service in billing.py under SPEC.md. Billing closes must retain prior postings while late corrections and tariff changes produce exact, replay-safe adjustments. Implement the reusable SQLite API and run the suite. You may add behavioral regression tests.

When finished, write claims JSON and invoke `submit --status complete --claims /tmp/claims.json` or `submit --status blocked --claims /tmp/claims.json` through bash. `submit` is a shell executable, not a separate agent tool.
