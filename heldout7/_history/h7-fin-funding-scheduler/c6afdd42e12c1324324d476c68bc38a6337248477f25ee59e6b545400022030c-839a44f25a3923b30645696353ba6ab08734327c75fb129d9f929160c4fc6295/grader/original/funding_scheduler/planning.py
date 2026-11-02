"""What-if planning used by the treasury dashboard.

``scenario_plans`` lists, for ONE scenario taken as known in advance, every vector
of current offers that keeps that scenario's limits. It is a diagnostic view of
each scenario on its own; it does not account for what is known when.
"""
from itertools import product
from .exposure import within_limits
from .offers import OfferAdapter


def scenario_plans(bundle, scenario_id):
    adapter = OfferAdapter(bundle)
    offers = adapter.current_offers(); accepted = adapter.accepted_commitments()
    scenario = next(s for s in bundle['scenarios'] if s['id'] == scenario_id)
    obligations = sorted(bundle['obligations'], key=lambda o: o['id'])
    plans = []
    for vector in product(*[adapter.choices(o['id']) for o in obligations]):
        assignment = dict(zip([o['id'] for o in obligations], vector))
        if all(within_limits(bundle, offers, accepted, assignment, scenario, k) for k in range(bundle['horizon'])):
            plans.append(assignment)
    return plans
