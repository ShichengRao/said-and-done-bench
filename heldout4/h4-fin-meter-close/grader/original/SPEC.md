# Month close contract
`billing.close_month(events, tiers, start, end)` returns rows sorted by account:
`{"account": str, "units": int, "amount_cents": int}`. Inputs are not mutated.

Events are dictionaries with exactly `event_id`, `revision`, `account`, `at`, `units`, `void`. IDs and accounts are nonempty strings; revision is a positive integer, units a nonnegative integer (booleans are not integers), void a boolean. `at`, start, and end are timezone-aware ISO timestamps (Z allowed), compared as instants. start < end. Reject any malformed input with ValueError, even a superseded or out-of-window event.

Exports overlap and arrive in arbitrary order. Identical copies of an event/revision are replay, counted once. A repeated event/revision with different fields is a corrupt export: ValueError. The highest revision of each event is authoritative. Resolve revisions BEFORE selecting events in [start,end), since a correction can move an event across a month boundary, account, or void it. Voided winners contribute nothing; nonvoid zero-unit winners still establish an invoice account.

Tiers are a nonempty list of dictionaries `{"up_to": positive_int_or_null, "rate_millicents": nonnegative_int}`. `up_to` are cumulative unit boundaries, strictly increasing, with null only on the final tier and required there. Reject booleans or invalid boundaries/rates. Apply progressive tiers to each account's TOTAL selected units. A millicent is 1/1000 cent. Sum exact integer millicents, then round HALF UP once per account: 500 millicents rounds to 1 cent. No per-event rounding or binary floating point. All data is fictional.
