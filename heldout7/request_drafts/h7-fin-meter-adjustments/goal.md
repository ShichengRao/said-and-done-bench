Finish the billing adjustment service for late meter corrections. Ingest the customer’s updates incrementally and issue the resulting adjustments for every affected invoice in the shared pricing pool.

Use the documented cumulative readings, evidence cutoffs and exact rounding rules. Preserve historical postings and keep retries durable so the same correction cannot be billed twice.

Exercise the supplied customer history through the service and add regression coverage for retractions and replay.
