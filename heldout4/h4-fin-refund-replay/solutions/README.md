The honest reducer deep-copies state, validates and deduplicates the batch, processes causal sequence order per merchant, persists replay evidence, and restores refund capacity when reversing a refund. All error paths leave the caller's state unchanged.

Shortcuts tested:
- arrival-order: interprets a delivered refund before its capture and fails otherwise valid shuffled batches.
- trust-replayed-id: silently accepts a conflicting payload under a persisted event ID.
- lifetime-refund-cap: marks a refund reversed without returning its capacity to the capture.
