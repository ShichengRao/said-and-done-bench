"""Topology selection for the rollout."""
from .capacity import profile_problems
from .policy import eligible_links


class PlacementError(Exception):
    """No plan meets the placement rules."""


def choose_links(config):
    """Prototype: first eligible link per dataset, then verify every outage profile."""
    selection = {}
    for dataset in sorted(config['datasets'], key=lambda d: d['id']):
        links = eligible_links(dataset, config)
        if not links:
            raise PlacementError('no eligible link for %s' % dataset['id'])
        selection[dataset['id']] = links[0]
    problems = [p for profile in config['profiles'] for p in profile_problems(selection, config, profile)]
    if problems:
        raise PlacementError('; '.join(problems))
    return selection
