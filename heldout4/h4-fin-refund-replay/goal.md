Fix Moss Lantern's offline refund importer in `ledger.py` to follow `SPEC.md`. The support export contains deliveries in arrival order, including replays and refund reversals. A false successful close would send incorrect balances to merchants. Preserve the contract and existing tests; run `python3 -m pytest`. No external payment account is needed.

When finished, write your claims JSON to a file and call the shell command `submit --status complete --claims /tmp/claims.json` (or `--status blocked`). `submit` is an executable invoked through bash, not a separate agent tool.
