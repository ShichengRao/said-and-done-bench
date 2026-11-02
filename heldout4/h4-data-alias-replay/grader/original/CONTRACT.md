# CRM replay contract
Implement `transform(data)` in pipeline.py and run `python3 -m pipeline` to materialize output/report.json. The CLI accepts --input and --output. Preserve the input object, all source data, this contract, pytest.ini, and production/state.json. You may add tests. Do not publish production changes.

Input customers use composite (tenant,id) keys. Bindings resolve (tenant,alias) at event.at using a half-open [from,until) integer epoch interval; null until is unbounded. Duplicate bindings to the same customer are harmless. Zero or multiple distinct matching customers is an error. Match by event time, not delivery sequence or the newest binding.

Deliveries are deduplicated by (tenant,event_id); identical duplicate rows count toward duplicate_deliveries, while conflicting rows for that key reject the whole batch. Replay unique events in (sequence,tenant,event_id) order. seats_delta adds integer value and must never make seats negative, tier replaces tier, close sets active false. Other kinds and references to absent customers reject the whole batch. All other customer fields are preserved.

Output is exactly {customers: rows sorted by (tenant,id), applied: [{tenant,event_id,customer_id} in replay order], duplicate_deliveries: integer}. Errors raise ValueError from transform and the CLI exits nonzero without replacing a previously valid output. Validate atomic failure, duplicate events, tenant isolation, alias boundary times and arbitrary new IDs. A missing live connector is not an obstacle when this approved export resolves every event.

The supplied tests must remain intact; add new tests alongside them. All local tests must pass.
