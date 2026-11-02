"""Binding funding schedule for the customer's new obligations.

``build_schedule(bundle)`` must return the schedule document described in the
README ("Schedule artifact") or raise ScheduleError when it cannot.
``check_schedule(bundle, schedule)`` returns a list of problems (empty when the
schedule can be executed in every covered scenario).
"""
from .errors import ScheduleError
from .exposure import within_limits
from .inspections import InspectionAdapter
from .offers import OfferAdapter


def build_schedule(bundle):
    raise ScheduleError('scheduler not implemented yet')


def _key(history):
    return tuple((f[0], f[1], tuple(tuple(r) for r in f[2])) for f in history)


def check_schedule(bundle, schedule):
    adapter = OfferAdapter(bundle)
    offers = adapter.current_offers(); accepted = adapter.accepted_commitments()
    inspections = InspectionAdapter(bundle, offers).with_commitments(accepted)
    problems = []
    nodes = {}
    for node in schedule.get('decisions', []):
        key = (node['stage'], _key(node['history']))
        value = tuple((a['obligation'], a['route']) for a in node['assignment'])
        if key in nodes and nodes[key] != value:
            problems.append('conflicting decisions for one observed history')
        nodes[key] = value
    for scenario in bundle['scenarios']:
        funded = {}
        for stage in range(bundle['horizon']):
            due = sorted(o['id'] for o in bundle['obligations'] if o['pay_stage'] == stage)
            if due:
                key = (stage, _key(inspections.history(scenario['id'], stage, funded)))
                if key not in nodes:
                    problems.append('no decision for %s at stage %d' % (scenario['id'], stage)); break
                chosen = dict(nodes[key])
                if sorted(chosen) != due or any(r not in offers or offers[r]['obligation'] != o for o, r in chosen.items()):
                    problems.append('invalid assignment for %s at stage %d' % (scenario['id'], stage)); break
                funded.update(chosen)
            if not within_limits(bundle, offers, accepted, funded, scenario, stage):
                problems.append('limit exceeded for %s at stage %d' % (scenario['id'], stage)); break
    return problems
