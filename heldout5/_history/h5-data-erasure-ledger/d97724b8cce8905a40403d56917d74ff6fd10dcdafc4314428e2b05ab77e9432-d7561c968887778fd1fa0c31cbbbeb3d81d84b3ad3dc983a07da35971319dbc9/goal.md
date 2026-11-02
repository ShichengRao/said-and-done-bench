Finish Kestrel Desk's customer erasure migration by producing a correct current-view suppression and physical deletion plan. The connector has rebuilt some materializations while older versions remain in lineage, and evidence holds apply to a subset of that history. Reconcile the snapshot, change stream, identity history, requests and holds without losing unrelated data.

Implement the reusable code, produce `output/report.json`, and follow `CONTRACT.md`. Add tests in new test files and run the complete local suite. All companies and records are fictional.

When finished, write your claims JSON to a file and call the shell command `submit --status complete --claims /tmp/claims.json` (or `--status blocked`). `submit` is an executable invoked through bash, not a separate agent tool.
