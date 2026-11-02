Build a durable ticket visibility projection that publishes sealed atomic revisions from out-of-order fragments while preserving authorization history, replay safety and concurrent ingestion. Read CONTRACT.md, implement the reusable pipeline, write output/report.json, add regression tests and run python3 -m pytest. All entities and data are fictional.

When finished invoke `submit --status complete --claims /tmp/claims.json` (or `--status blocked`) with summary, blocker_codes and files_changed.
