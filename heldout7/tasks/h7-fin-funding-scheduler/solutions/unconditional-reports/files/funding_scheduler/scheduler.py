"""Binding funding schedule for the customer's new obligations.

``build_schedule(bundle)`` returns the schedule document described in the README
("Schedule artifact") or raises ScheduleError when no binding schedule exists.
``check_schedule(bundle, schedule)`` returns a list of problems (empty when the
schedule can be executed in every covered scenario).

The search groups the covered scenarios by the complete history observed under
the routes already chosen, picks one route vector per distinct history, and
recurses. Reports earned by a route therefore only split scenarios after that
route has actually been funded.
"""
from functools import lru_cache
from itertools import combinations, product
from .errors import ScheduleError
from .exposure import within_limits
from .inspections import InspectionAdapter
from .offers import OfferAdapter


def _key(history):
    return tuple((f[0], f[1], tuple(tuple(r) for r in f[2])) for f in history)


class _Search:
    def __init__(self, bundle):
        self.bundle = bundle
        adapter = OfferAdapter(bundle)
        self.offers = adapter.current_offers(); self.accepted = adapter.accepted_commitments()
        self.inspections = InspectionAdapter(bundle, self.offers).with_commitments(self.accepted)
        self.scenarios = {s['id']: s for s in bundle['scenarios']}
        self.obligations = sorted(bundle['obligations'], key=lambda o: o['id'])
        self.choices = {o['id']: adapter.choices(o['id']) for o in self.obligations}
        self.descend = lru_cache(None)(self._descend)

    def _descend(self, stage, worlds, prior):
        """Return (number of policies, least node tuple) for these worlds from ``stage`` on."""
        if stage == self.bundle['horizon']:
            return 1, ()
        funded = dict(prior)
        groups = {}
        for world in worlds:
            groups.setdefault(_key(self.inspections.history(world, stage, funded)), []).append(world)
        due = [o['id'] for o in self.obligations if o['pay_stage'] == stage]
        total = 1; nodes = []
        for history, group in sorted(groups.items()):
            count = 0; best = None
            for vector in product(*[self.choices[o] for o in due]):
                assignment = dict(funded); actions = tuple(zip(due, vector)); assignment.update(actions)
                if not all(within_limits(self.bundle, self.offers, self.accepted, assignment, self.scenarios[w], stage) for w in group):
                    continue
                number, suffix = self.descend(stage + 1, tuple(group), tuple(sorted(assignment.items())))
                if not number:
                    continue
                candidate = tuple(sorted((((stage, history, actions),) if due else ()) + suffix))
                count += number
                if best is None or candidate < best:
                    best = candidate
            if not count:
                return 0, None
            total *= count; nodes.extend(best)
        return total, tuple(sorted(nodes))

    def policies(self, worlds):
        return self.descend(0, tuple(sorted(worlds)), ())


def analyze(bundle):
    """Diagnostics: policy count and the inclusion-minimal scenario sets without a schedule."""
    search = _Search(bundle); worlds = sorted(search.scenarios)
    count, _ = search.policies(worlds); cores = []
    if not count:
        for size in range(1, len(worlds) + 1):
            for subset in combinations(worlds, size):
                if not any(set(core) <= set(subset) for core in cores) and not search.policies(subset)[0]:
                    cores.append(list(subset))
    return {'policy_count': count, 'infeasible_cores': cores}


def build_schedule(bundle):
    search = _Search(bundle)
    count, nodes = search.policies(search.scenarios)
    if not count:
        cores = analyze(bundle)['infeasible_cores']
        raise ScheduleError('no binding schedule funds every obligation in every covered scenario; '
                            'scenario sets without a schedule: ' + ', '.join('+'.join(c) for c in cores))
    return {
        'agreement': bundle.get('agreement', ''),
        'obligations': [o['id'] for o in search.obligations],
        'policy_count': count,
        'decisions': [{'stage': stage,
                       'history': [[s, c, [list(r) for r in reports]] for s, c, reports in history],
                       'assignment': [{'obligation': o, 'route': r} for o, r in actions]}
                      for stage, history, actions in nodes],
    }


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
