Build the durable ticket visibility index for the customer connector. It needs to consume out-of-order revision fragments and publish coherent document, access-control and membership updates as sealed revisions become available.

Preserve historical visibility, keep incomplete revisions pending and make retries and concurrent ingestion safe across process restarts.

Connect the projection to the existing ingestion API and add regression coverage for delayed fragments, rollback and replay. The customer replay is `python -m ticket_index.replay`, which writes `output/index.json`; `README.md` defines the API and snapshot format.
