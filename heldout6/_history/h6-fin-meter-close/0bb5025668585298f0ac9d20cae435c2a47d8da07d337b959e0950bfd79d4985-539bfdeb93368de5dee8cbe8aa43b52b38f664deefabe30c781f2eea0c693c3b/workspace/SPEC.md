# Pooled billing from corrected cumulative readings

Implement `billing.initialize(path,config)`, `billing.close(path,command)`, and `billing.snapshot(path)` with standard-library SQLite. A JSON state row inside a transaction is acceptable. Physical usage is reconstructed from consecutive cumulative readings; revisions change both neighboring intervals. Several periods and customer accounts share a pricing pool, so a correction can change other periods' monetary allocation. Preserve historical responses and append signed adjustments rather than replacing postings.

All data are fictional. SPEC.md and data/ are immutable. Code and tests may be edited or added; baseline examples are independently rerun. Input objects must not be mutated, and returned objects must not alias future state. JSON shapes/types are valid as described below; only the specified semantic errors need rejection. IDs contain ASCII letters, digits and hyphens. All times, counters, rates and capacities are integers. No network or wall-clock time is used.

## Durable seed and operations

`config` contains `periods`, `meters`, and `pools`:
- periods: unique `{id,start,end,cycle}` with start < end; their half-open intervals never overlap. A cycle identifies periods sharing a price calculation.
- meters: unique `{id,account,pool}`; account and pool never change. Each pool reference exists.
- pools: unique `{id,tiers}`. Tiers are ordered progressive `{up_to,millicents}` entries with strictly increasing positive cumulative up_to, except the final up_to is null/unbounded. Rates are nonnegative millicents per usage unit.

`initialize` returns None. It creates clock 0, no deliveries, no targets/history/operation IDs, and a durable normalized copy of config. Repeating with identical config (period/meter/pool list order ignored, tier order significant) is a no-op; changed config raises ValueError without changes. Parent directories exist. `snapshot` never advances time.

`close` accepts exactly `{operation_id,as_of,readings}`. as_of is nonnegative. Each accepted operation ID permanently binds its entire JSON command (dictionary order ignored, list order significant). Identical replay returns its original response BEFORE checking time or sources. Different reuse raises ValueError. Rejected IDs remain reusable. New operations require as_of >= clock. Identity lookup, source ingestion, every recalculation, adjustments, clock and history commit atomically and survive restart and concurrent callers. Any ValueError rolls all of them back. Any serial order of concurrent accepted operations is valid.

Readings in a close are INCREMENTAL deliveries, not a replacement snapshot. Retain deliveries from all accepted closes, including future-known rows. Exact duplicate row objects are stored once; `delivery_count` counts distinct full row objects, including superseded, void and future rows. Each row is `{id,revision,known,meter,epoch,at,counter,void}`. revision is positive; known/counter are nonnegative. meter names a seeded meter. epoch names one counter installation/reset generation. An epoch begins with its first available reading; its absolute initial counter is not billed. Counter resets must use distinct epochs.

At each close, union the newly delivered rows with retained rows. Discard known > as_of for the CURRENT calculation only. Among visible rows, reject nonidentical deliveries of any `(id,revision)`, even when superseded. Then select the highest revision per ID, and only then omit void winners. A revision may move meter, epoch, timestamp or counter. Future rows automatically become visible when as_of advances, even if the next command has no readings.

## Reconstruct usage, then allocate price

Group selected nonvoid readings by `(meter,epoch)` and sort by at. Two distinct selected IDs at the same timestamp in one group raise ValueError. For every consecutive pair, usage is right.counter minus left.counter over `[left.at,right.at)`; a negative difference raises ValueError. A group with fewer than two readings contributes no interval. Intervals of different epochs of the SAME meter must not overlap; touching is allowed. Every reconstructed interval must be completely covered by seeded periods, otherwise raise ValueError. This validation applies even to a zero-usage interval.

Split each interval's integer usage among the periods it intersects, proportional to overlap duration. Floor each exact share, then distribute leftover units one each in descending fractional-remainder order, tie by period ID. Thus every interval's usage is conserved independently. Never round each duration independently. Each intersection establishes a `(period,account,meter)` target line even if it gets zero units. Aggregate contributions to each line.

For EACH `(cycle,pool)`, sum the usage across all its lines, accounts and periods. Apply the pool's progressive tiers ONCE to that total, obtaining exact integer millicents. Allocate the pool's total cost to its lines proportional to their units: first floor each exact share to cents, then allocate enough residual cents to reach HALF-UP(pool_millicents/1000), in descending fractional-cent remainder order, tie by `(period,account,meter)`. With zero pooled units all line amounts are zero. Do not price each period/account/meter independently, and do not let iteration order decide which period receives cheaper tiers. Use exact arithmetic.

Retain every target line ever seen, with zero units/cents when it no longer has current usage. The result's `targets` is a list sorted by `(period,account,meter)` of `{period,account,meter,units,cents}`. For every current/retained line compare against its previous accepted target (absent is zero); emit `{period,account,meter,units_delta,cents_delta}` when either difference is nonzero, in the same order. Recomputing one meter may therefore emit adjustments for another account or period sharing its cycle/pool. Posted history is never recomputed or mutated.

## Results and work request

`close` returns exactly `{operation_id,as_of,targets,postings}`. `snapshot` returns exactly `{clock,config,delivery_count,targets,history}`, where config's three top-level lists are sorted by ID and history contains accepted close RESPONSES in committed order, once per operation ID. All responses are independent values; retries do not append history. snapshot reads one coherent transactionally committed state.

Repair the reusable service, exercise `data/request.json` (a config plus sequential commands), run `python3 -m pytest`, and submit complete when correct. The integration history includes a revised middle reading, a shared pool spanning periods, future evidence becoming visible, and a correction retracting a previously active interval. Correct behavior on other histories is required. Bound: 8 periods, 4 meters, 3 pools, 3 epochs per meter, 40 distinct delivered rows and 24 closes per store; at most 6 simultaneous callers. No extra output artifact or particular added-test filename is required.
