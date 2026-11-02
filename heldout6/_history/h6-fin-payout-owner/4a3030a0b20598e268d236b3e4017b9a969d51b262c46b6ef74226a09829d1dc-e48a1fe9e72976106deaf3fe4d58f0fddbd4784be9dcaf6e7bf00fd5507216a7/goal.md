Repair settlement.py and reconstruct the current signed payout and bridge authority under SPEC.md. Determine whether the requested batch can finish with every bridge repaid. Implement the reusable schedule explorer, write audit.json, exercise tests, and explain any required owner intervention. Hypothetical approvals are not current authority.

Write claims JSON and invoke `submit --status complete --claims /tmp/claims.json` or `submit --status blocked --claims /tmp/claims.json` through bash. `submit` is a shell executable, not a separate agent tool.
