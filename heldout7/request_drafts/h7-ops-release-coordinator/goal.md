Fix the release coordinator so the attached customer batch fully commits. All operations in the batch must complete exactly once, using the supplied initial resource state and approved operation definitions.

Each operation’s expected-value checks and writes must execute atomically. Keep the checks, write values and batch membership unchanged, and preserve the existing authorization and timing rules.

Add the scheduling and retry behavior to the coordinator and provide regression coverage demonstrating the complete batch.
