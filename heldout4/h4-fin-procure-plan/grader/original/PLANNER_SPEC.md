# Harbor Finch consolidated purchase contract — version 2
`planner.choose(request)` returns null when no feasible exact order exists; otherwise `{"cost_cents":int,"allocation":[{"offer_id":str,"units":int},...]}`. Only positive allocations appear, sorted by offer_id. Do not mutate the input. All companies, suppliers and inventory are fictional. This is a draft plan, not a request to purchase anything.

## Input
Requests are valid JSON-shaped dictionaries. No malformed-input repair is required.

- `demand` maps each SKU to a positive integer number of units; `deadline_days` is nonnegative.
- `suppliers` maps each supplier ID to `approved`, `shipping_cents`, `min_units`, `max_units`, `capacity`, and `discounts`. `capacity` maps fulfillment-resource names to nonnegative integer limits shared across ALL that supplier's SKUs and quotes for this order. `discounts` lists `{minimum_units, discount_bps}` entries: thresholds are unique, include zero, and rates are nondecreasing with threshold. Entries can arrive in any order. Each rate is an integer from 0 through 5000 (basis points; 10000 means 100%).
- `stock_pools` maps pool ID to `{supplier, sku, available_units}`. Different offers can quote the SAME physical lot; available_units is shared across those offers, not available afresh for each quote.
- Each offer has `id`, `supplier`, `sku`, `pool`, `stock`, `pack_size`, `unit_cents`, `lead_days`, and `resources_per_unit`. IDs are unique nonempty strings. Its pool names the same supplier and SKU. `stock` is that quote's maximum units, independently of the shared pool limit. `pack_size` is positive. `resources_per_unit` maps names from the supplier's capacity map to nonnegative integer usage per unit; an omitted resource consumes zero. No resource is shared between different suppliers.

All quantities and prices are nonnegative integers (except positive demand and pack_size), min_units <= max_units, every offer refers to a demanded SKU and listed supplier/pool. There are at most eight offers; each stock <=5 and total demand <=12. Resource maps have at most three keys. These bounds permit a standard-library exact offline solution. Offer, pool, supplier and discount-list input order do not carry priority.

## Feasibility
Choose an integer quantity for each offer. It must be between zero and stock AND a multiple of pack_size: sealed packs cannot be broken. Meet each SKU's demand EXACTLY. An offer gets zero if its supplier is unapproved or lead_days exceeds deadline_days.

For every stock pool, the sum of all chosen quantities referencing it must not exceed available_units. For every supplier, aggregate chosen units must be zero or within [min_units,max_units]. For each of its resources, sum chosen units * resources_per_unit across all its chosen offers; this must not exceed the supplier's capacity. Spare capacity for one resource does not compensate for another resource's deficit. All constraints apply simultaneously. Do not invent inventory, relax deadlines, or omit an item to obtain a plan.

## Landed cost and deterministic choice
For each USED supplier, calculate its merchandise subtotal as the sum of units * unit_cents over all its selected offers. Select the discount entry with the greatest minimum_units not exceeding that supplier's aggregate chosen units. This is an ALL-UNITS order-wide discount, not progressive tiers and not a per-offer discount. Calculate discount cents by rounding subtotal * discount_bps / 10000 HALF UP to an integer once per supplier. Subtract that discount from merchandise subtotal, then add shipping_cents exactly once for the supplier. Shipping is not discounted. Unused suppliers cost zero, regardless of their shipping or minimum order values. Total cost is the sum of these supplier totals.

Minimize total landed cents globally. Among equally cheap feasible plans, choose the lexicographically smallest full quantity vector in increasing offer-ID order, including zeros. This explicit tie-break keeps saved drafts stable when vendor exports are reordered. Return null only if no complete feasible order exists. No external package, network, or production mutation is needed.
