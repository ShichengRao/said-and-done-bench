"""Topology selection for the rollout: one committed link per dataset that
survives every outage profile under the current leases."""
from .capacity import profile_problems
from .policy import eligible_links


class PlacementError(Exception):
    """No plan meets the placement rules."""


def candidate_plans(config, profiles):
    datasets = sorted(config['datasets'], key=lambda d: d['id'])
    options = [(d['id'], eligible_links(d, config)) for d in datasets]
    chosen = {}

    def visit(index):
        if index == len(options):
            yield dict(chosen)
            return
        dataset_id, links = options[index]
        for link in links:
            chosen[dataset_id] = link
            # prune: the partial selection must already fit every profile
            if not any(profile_problems(chosen, config, p) for p in profiles):
                yield from visit(index + 1)
            del chosen[dataset_id]
    yield from visit(0)


def choose_links(config):
    for dataset in config['datasets']:
        if not eligible_links(dataset, config):
            raise PlacementError('no eligible link for %s' % dataset['id'])
    plan = next(candidate_plans(config, config['profiles']), None)
    if plan is not None:
        return plan
    singles = {p['id']: list(candidate_plans(config, [p])) for p in config['profiles']}
    tightest = min(singles, key=lambda name: (len(singles[name]), name))
    details = []
    for option in singles[tightest][:3]:
        failures = [problem for p in config['profiles'] for problem in profile_problems(option, config, p)]
        details.append('%s fails: %s' % (option, '; '.join(failures)))
    raise PlacementError('no committed topology fits every outage profile; plans per profile alone: %s; %s'
                         % (', '.join('%s=%d' % (k, len(v)) for k, v in sorted(singles.items())), ' | '.join(details)))
