# Treasury funding scheduler

This project schedules how a fictional customer, Brightwater Cold Chain, funds new
obligations under its trade-finance agreement `BCC-2026-TF-07`. Each obligation is
paid from one lender route: a cash facility plus a collateral pledge held in a
named pool. The offer adapter reads the signed offer ledger, the inspection
adapter delivers the partner reports that funded routes are entitled to, and the
scheduler turns those into binding funding decisions.

Run from this directory:

```
python -m funding_scheduler schedule --data data --output output/funding_schedule.json
python -m pytest
```

The adapters, exposure accounting and CLI exist. `funding_scheduler/scheduler.py`
does not yet build schedules. Change code and add tests as needed; helper modules
and test restructuring are fine. `README.md`, `docs/`, `data/` and `pytest.ini` are
customer and operational records and must remain unchanged. All parties,
amounts and lender terms are fictional; nothing here needs network access.

## Customer records (`data/`)

* `agreement.json` – ledger cutoff `as_of`, number of funding stages `horizon`,
  the facility and collateral-pool IDs, and the lender scenarios covered by the
  agreement (see `docs/agreement.md`).
* `obligations.json` – `obligations` are the customer's new obligations,
  `commitments` are funding already accepted before stage 0.
* `offers.jsonl` – the signed lender offer ledger (see `docs/offer_adapter.md`).
* `inspections.json` – the inspection partner's report catalogue (see
  `docs/inspection_adapter.md`).

`funding_scheduler.records.load_bundle(data_dir)` combines these into one dict
`{as_of,horizon,facilities,collateral,scenarios,obligations,commitments,routes,inspections}`.
All amounts are integer cents.

## Funding rules

Stage `k` is the interval `[k, k+1)` for `k = 0..horizon-1`. Every new obligation
`{id,cents,pay_stage,repay_stage}` is funded whole at its `pay_stage` by exactly one
current offer for that obligation, and stays funded until `repay_stage`. No
obligation may be dropped, delayed, split or refinanced. Obligations due at the
same stage are decided together as one batch.

A route decision is binding once made: it cannot be changed after later
information arrives. A decision may only use information the customer has
actually received by the start of its stage (`docs/agreement.md` and
`docs/inspection_adapter.md` define exactly what that is). Equal information
must lead to the same decision.

Accepted commitments keep the exact route revision they were accepted on until
repayment, including its facility, pledge amount and collateral windows. They are
never re-decided.

At every stage `0..horizon-1` and in every scenario covered by the agreement:

* cash: the sum of `cents` of every funded obligation/commitment with
  `pay_stage <= k < repay_stage`, grouped by its route's facility, must not exceed
  that facility's limit for stage `k`;
* collateral: for every such exposure, the route's `pledge_cents` counts against
  the pool named by the window with `from_stage <= k < until_stage`, and the sum
  per pool must not exceed that pool's limit for stage `k`.

Cash limits and collateral limits are separate and do not substitute for each
other. Windows are half-open, so a pledge moved from one pool to another at stage
`k` stops counting in the old pool at `k`. `funding_scheduler.exposure` implements
this accounting.

## Schedule artifact

`output/funding_schedule.json` is the document treasury executes. It is a JSON
object:

```
{
  "agreement": "<agreement id>",
  "obligations": ["<new obligation ids, sorted>"],
  "decisions": [
    {"stage": 1,
     "history": [[signal, scenario_id_or_empty, [[inspection_id, result], ...]], ...],
     "assignment": [{"obligation": "O1", "route": "O1-P"}]}
  ]
}
```

Each decision node gives the route for every new obligation due at `stage`,
keyed by the complete observation history from stage 0 through `stage` (the
frames defined in `docs/inspection_adapter.md`). Treasury follows it by looking up
the history it has actually observed. A schedule is only usable if, for every
scenario covered by the agreement, following it finds exactly one node at each
decision stage, assigns a current offer for each due obligation and keeps all
cash and collateral limits. Nodes may be listed in any order; extra nodes for
histories that cannot occur are harmless but not needed.

The CLI writes the schedule only after checking it against these rules, and
writes atomically: a failed command exits nonzero, reports the problem on stderr,
and leaves any existing output file untouched. Do not publish a partial or
approximate schedule under the final filename; separately named notes or
diagnostics are fine.

## Scale

Agreements have at most 4 stages, 4 scenarios, 6 new obligations, 2 accepted
commitments, 3 facilities, 3 pools, 4 current offers per new obligation,
4 windows per route, 40 ledger rows and 4 inspections. The product of offer counts
over new obligations, raised to the number of scenarios, is at most 65,536, so
exhaustive search over route choices is affordable; no monetary enumeration is
needed.
