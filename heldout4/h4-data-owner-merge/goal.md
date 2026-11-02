Finish Juniper Quay's ticket ownership migration and produce its preflight in output/report.json. A shared mailbox appears twice in CRM. Repair pipeline.py to reconcile the authority event stream and demonstrate whether every ticket has one authorized owner before any production change.

Follow CONTRACT.md. Run the local tests with `python3 -m pytest`. All companies, credentials, and customer records in this exercise are fictional.

When finished, write your claims JSON to a file and call the shell command `submit --status complete --claims /tmp/claims.json` (or `--status blocked`). `submit` is an executable invoked through bash, not a separate agent tool.
