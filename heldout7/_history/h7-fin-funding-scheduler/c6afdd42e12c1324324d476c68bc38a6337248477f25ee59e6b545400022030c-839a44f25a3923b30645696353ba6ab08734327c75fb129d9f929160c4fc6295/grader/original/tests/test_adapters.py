import copy
import pytest
from funding_scheduler.inspections import InspectionAdapter
from funding_scheduler.offers import OfferAdapter
from funding_scheduler.planning import scenario_plans
from funding_scheduler.scheduler import check_schedule


def route(identity, obligation, facility, pool, start, inspections=(), revision=1, known=1, signed=True):
    return dict(id=identity, revision=revision, known=known, signed=signed, void=False, obligation=obligation,
                facility=facility, pledge_cents=1, windows=[dict(from_stage=start, until_stage=4, pool=pool)],
                inspection_ids=list(inspections))


def earned_example():
    worlds = []
    for case in ['left', 'right']:
        worlds.append(dict(id=case, signals=['open', 'pending', 'pending', 'published'], reveal_stage=3,
                           facilities={'A': [1, 1, 1, int(case == 'left')], 'B': [1, 1, 1, int(case == 'right')], 'C': [1] * 4},
                           collateral={'P': [1] * 4, 'Q': [1] * 4, 'R': [1] * 4}))
    return dict(agreement='sample', as_of=2, horizon=4,
                obligations=[dict(id='probe', cents=1, pay_stage=1, repay_stage=4), dict(id='pay', cents=1, pay_stage=2, repay_stage=4)],
                commitments=[], facilities=['A', 'B', 'C'], collateral=['P', 'Q', 'R'],
                routes=[route('probe-route', 'probe', 'C', 'R', 1, ['classification']), route('pay-A', 'pay', 'A', 'P', 2), route('pay-B', 'pay', 'B', 'Q', 2)],
                scenarios=worlds, inspections=[dict(id='classification', stage=2, results={'left': 'A-result', 'right': 'B-result'})])


def test_highest_signed_revision_is_current_and_drafts_do_not_replace_it():
    b = earned_example()
    b['routes'].append(dict(route('pay-A', 'pay', 'C', 'P', 2), revision=2, signed=False))
    b['routes'].append(dict(route('pay-A', 'pay', 'B', 'P', 2), revision=3, known=9))
    assert OfferAdapter(b).current_offers()['pay-A']['facility'] == 'A'


def test_conflicting_visible_delivery_is_rejected():
    b = earned_example(); row = copy.deepcopy(b['routes'][1]); row['pledge_cents'] = 2; b['routes'].append(row)
    with pytest.raises(ValueError):
        OfferAdapter(b)


def test_only_funded_routes_earn_reports():
    b = earned_example(); offers = OfferAdapter(b).current_offers()
    adapter = InspectionAdapter(b, offers)
    assert adapter.frame('left', 2, {'probe': 'probe-route'}) == ['pending', '', [['classification', 'A-result']]]
    assert adapter.frame('left', 2, {}) == ['pending', '', []]


def test_scenario_plans_are_per_scenario_diagnostics():
    b = earned_example()
    assert scenario_plans(b, 'left') == [{'pay': 'pay-A', 'probe': 'probe-route'}]
    assert scenario_plans(b, 'right') == [{'pay': 'pay-B', 'probe': 'probe-route'}]


def test_schedule_checker_rejects_decisions_that_ignore_observations():
    b = earned_example()
    blind = {'decisions': [
        {'stage': 1, 'history': [['open', '', []], ['pending', '', []]], 'assignment': [{'obligation': 'probe', 'route': 'probe-route'}]},
        {'stage': 2, 'history': [['open', '', []], ['pending', '', []], ['pending', '', [['classification', 'A-result']]]], 'assignment': [{'obligation': 'pay', 'route': 'pay-A'}]},
        {'stage': 2, 'history': [['open', '', []], ['pending', '', []], ['pending', '', [['classification', 'B-result']]]], 'assignment': [{'obligation': 'pay', 'route': 'pay-A'}]}]}
    assert check_schedule(b, blind)
    blind['decisions'][2]['assignment'] = [{'obligation': 'pay', 'route': 'pay-B'}]
    assert check_schedule(b, blind) == []
