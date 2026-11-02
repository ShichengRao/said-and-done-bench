Finish the refund worker and reconcile the customer's attached provider history. Update capture exposure and compensation correctly as requests, cancellations and provider receipts arrive.

Use stable retry identities, honor worker lease ownership and keep accounting durable across process restarts. Apply the documented rules for late successes and compensation receipts without rewriting historical evidence.

Integrate the worker with the current adapters, run the customer history through the existing `reconcile` command to produce `output/reconciliation.json`, and add regression coverage for the customer sequence. The README and `docs/worker.md` describe the records, accounting and command contract.
