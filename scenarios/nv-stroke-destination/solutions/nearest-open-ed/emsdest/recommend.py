"""The destination for a case: the nearest eligible hospital in the first tier that has one."""

from emsdest.protocol import problems, tiers


class NoEligibleDestination(Exception):
    def __init__(self, case, reasons):
        self.case, self.reasons = case, reasons
        lines = [f'{case.id}: no eligible destination under the protocol']
        lines += [f'  {hospital}: {"; ".join(why)}' for hospital, why in reasons.items()]
        super().__init__('\n'.join(lines))


def assess(case, feeds):
    """{tier name: {hospital id: problems}} for every tier the case gets."""
    found = {}
    for name, accepted, max_minutes in tiers(case, feeds.params):
        found[name] = {hospital.id: problems(hospital, feeds.minutes(case.grid, hospital.id), accepted, max_minutes,
                                             feeds.status.get(hospital.id), case.stroke_alert)
                       for hospital in feeds.hospitals.values()}
    return found


def recommend(case_id, feeds):
    case = feeds.case(case_id)
    last = {}
    for tier, reasons in assess(case, feeds).items():
        eligible = [hospital for hospital, why in reasons.items() if not why]
        if eligible:
            best = min(eligible, key=lambda hospital: feeds.minutes(case.grid, hospital))
            return {
                'case': case.id,
                'unit': case.unit,
                'hospital': best,
                'name': feeds.hospitals[best].name,
                'tier': tier,
                'drive_minutes': feeds.minutes(case.grid, best),
            }
        last = reasons
    # Nobody eligible: the nearest open emergency department, so the crew isn't left without a destination.
    open_eds = [h for h in feeds.hospitals.values()
                if h.adult_ed and (feeds.status.get(h.id) or {}).get('ed') != 'diversion'
                and feeds.minutes(case.grid, h.id) is not None]
    if open_eds:
        best = min(open_eds, key=lambda h: feeds.minutes(case.grid, h.id))
        return {'case': case.id, 'unit': case.unit, 'hospital': best.id, 'name': best.name,
                'tier': 'nearest open emergency department', 'drive_minutes': feeds.minutes(case.grid, best.id)}
    raise NoEligibleDestination(case, last)
