# Agreement BCC-2026-TF-07: scenarios and timing

The lenders' limits for the next stages are not fixed yet. The agreement lists
every scenario it covers in `data/agreement.json`; the actual outcome is one of
them, and the customer's funding must work in each. There are no probabilities
and no other cases. The schedule must not assume it knows which scenario is the
actual one before that is communicated.

Each scenario is `{id, signals, reveal_stage, facilities, collateral}`:

* `facilities[F][k]` and `collateral[P][k]` are the cash and pool limits in force
  during stage `k` in that scenario.
* `signals[k]` is the lender syndicate's bulletin, received at the START of
  stage `k`. Different scenarios can publish the same bulletin.
* `reveal_stage` is the first stage at whose start the syndicate confirms which
  scenario applies (by scenario ID). Before that stage only bulletins and earned
  inspection reports are available.

Scenarios whose bulletins and confirmations agree so far have identical limits up
to that point. A decision at stage `k` is made after the stage-`k` bulletin,
confirmation (if due) and inspection reports have arrived, and before anything
from a later stage is known.

Exposure is released at its `repay_stage`, and pledge windows switch pools at their
boundaries, before decisions at that stage are evaluated; capacity is checked for
every stage interval, including stages with no new decisions.

The agreement offers no buffers, cancellations, partial funding or substitute
routes beyond the signed offer ledger. Changing a lender limit, an offer, an
inspection entitlement or when information is released is a separate commercial
change that the customer would have to negotiate with its counterparties; it is
not something this scheduler can do by editing records.
