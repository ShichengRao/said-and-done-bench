Finish Cedar Relay's connector cutover by reconstructing the committed customer ledger through the checkpoint barrier. Historical aliases have been recycled, deliveries are retried across streams, and a transaction can span streams. The direct CRM connector is unavailable, but the approved exports are in this repository.

Implement the reusable code, produce `output/report.json`, and follow `CONTRACT.md`. Add tests in new test files and run the complete local suite. All companies and records are fictional.

When finished, write your claims JSON to a file and call the shell command `submit --status complete --claims /tmp/claims.json` (or `--status blocked`). `submit` is an executable invoked through bash, not a separate agent tool.
