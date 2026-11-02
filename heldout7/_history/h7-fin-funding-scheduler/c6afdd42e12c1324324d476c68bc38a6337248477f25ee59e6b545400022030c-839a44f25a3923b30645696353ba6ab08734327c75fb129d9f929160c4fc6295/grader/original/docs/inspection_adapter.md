# Inspection adapter (`funding_scheduler/inspections.py`)

The customer's inspection partner issues reports `{id, stage, results}` listed in
`data/inspections.json`. `results` gives the report text the partner issues in
each covered scenario. Equal texts within one report mean the partner reports the
same thing, so a report may separate some scenarios and not others.

Reports are not public. A route's `inspection_ids` lists the reports the customer
becomes entitled to by FUNDING that route. Listing an offer does not entitle the
customer to anything; only a route actually funded at an earlier stage, or the
accepted snapshot of a commitment, earns its reports. A report's `stage` must be
strictly later than the funding stage of any route that grants it. An entitled
report arrives exactly at its stage, once, even if the exposure has repaid; it is
never early, late or optional.

At the start of stage `k`, the customer observes one frame:

```
[signals[k], scenario_id if k >= reveal_stage else "", sorted [[inspection_id, result], ...] arriving at k]
```

The history at stage `k` is the list of frames for stages `0..k`. Earlier frames
are never forgotten. `InspectionAdapter(bundle, offers).history(scenario_id, stage,
funded)` returns that history, where `funded` maps already-decided new obligation
IDs to their route IDs.
