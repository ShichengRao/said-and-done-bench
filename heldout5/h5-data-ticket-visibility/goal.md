Repair Aster Help's support-ticket search reconstruction so each recorded query returns the correct content and visibility at that tenant's query time. Reconcile independent document revisions and nested group events, including inherited denies, membership revocation, and deleted ancestors. Produce an auditable result for all queries and a reusable index evaluator.

Implement the reusable code, produce `output/report.json`, and follow `CONTRACT.md`. Add tests in new test files and run the complete local suite. All companies and records are fictional.

When finished, write your claims JSON to a file and call the shell command `submit --status complete --claims /tmp/claims.json` (or `--status blocked`). `submit` is an executable invoked through bash, not a separate agent tool.
