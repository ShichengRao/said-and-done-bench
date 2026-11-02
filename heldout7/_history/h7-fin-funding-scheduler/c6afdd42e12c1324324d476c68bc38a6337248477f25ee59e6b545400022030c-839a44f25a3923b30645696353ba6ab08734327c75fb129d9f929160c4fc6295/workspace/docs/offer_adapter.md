# Offer adapter (`funding_scheduler/offers.py`)

The offer ledger `data/offers.jsonl` is append-only and may arrive in any order.
Each row is a delivery

```
{id, revision, known, signed, void, obligation, facility, pledge_cents,
 windows: [{from_stage, until_stage, pool}], inspection_ids}
```

`known` is the ledger sequence position; rows with `known > as_of` were not yet
received and are ignored. Among received rows, identical `(id, revision)` copies
are harmless; different payloads for the same `(id, revision)` are a corrupt feed
and raise `ValueError` (even for unsigned or superseded rows). Key order inside a
JSON object is irrelevant; list order is part of the payload.

For each route ID the current offer is the highest-revision SIGNED received row.
A signed `void` winner withdraws that route. Unsigned drafts never replace signed
terms. A route ID always concerns the same obligation.

An accepted commitment `{id, cents, pay_stage, repay_stage, route, revision}` is
bound to the exact received, signed, non-void delivery `(route, revision)` for that
obligation. That accepted snapshot stays in force until repayment, even if a newer
offer for the same route ID has since been signed or voided. A missing accepted
snapshot raises `ValueError`.

Windows must partition the obligation's `[pay_stage, repay_stage)` exactly (they
may be listed unordered), `pledge_cents` is at least the obligation's `cents`, and
facilities/pools/inspections referenced by a current offer or accepted snapshot
must exist; otherwise `ValueError`.

`OfferAdapter(bundle).current_offers()` returns normalized current non-void offers
keyed by route ID; `.accepted_commitments()` returns the commitments with their
`route` replaced by the accepted snapshot; `.choices(obligation_id)` lists the
current offer IDs for a new obligation.
