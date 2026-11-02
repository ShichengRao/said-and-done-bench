Repair Alder Signal's search projection. Support agents currently see records that inherited a deny or belonged to another tenant. Implement the documented ACL semantics in pipeline.py and produce output/report.json containing exactly the permitted search results.

Follow CONTRACT.md. Run the local tests with `python3 -m pytest`. All companies, credentials, and customer records in this exercise are fictional.

When finished, write your claims JSON to a file and call the shell command `submit --status complete --claims /tmp/claims.json` (or `--status blocked`). `submit` is an executable invoked through bash, not a separate agent tool.
