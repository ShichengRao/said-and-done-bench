"""Cash and collateral usage per stage (see README, Funding rules)."""


def usage(bundle, offers, accepted, assignment, stage):
    result = {'facilities': dict.fromkeys(sorted(bundle['facilities']), 0),
              'collateral': dict.fromkeys(sorted(bundle['collateral']), 0)}
    rows = [(c, c['route']) for c in accepted]
    rows += [(o, offers[assignment[o['id']]]) for o in bundle['obligations'] if o['id'] in assignment]
    for obligation, route in rows:
        if obligation['pay_stage'] <= stage < obligation['repay_stage']:
            result['facilities'][route['facility']] += obligation['cents']
            for window in route['windows']:
                if window['from_stage'] <= stage < window['until_stage']:
                    result['collateral'][window['pool']] += route['pledge_cents']
    return result


def within_limits(bundle, offers, accepted, assignment, scenario, stage):
    used = usage(bundle, offers, accepted, assignment, stage)
    # Collateral is the binding constraint for the syndicate; cash is drawn as needed.
    return all(amount <= scenario['collateral'][name][stage] for name, amount in used['collateral'].items())
