"""The destination protocol's rules (protocols/destination.md), as code."""

from datetime import timedelta


def suspected_lvo(case, params):
    """Rule 1: a stroke alert with a LAMS at or over the threshold, last known well within the window."""
    if not case.stroke_alert or case.lams is None or case.last_known_well is None:
        return False
    window = timedelta(hours=params['stroke']['lvo_window_h'])
    return case.lams >= params['stroke']['lams_lvo_threshold'] and case.reported_at - case.last_known_well <= window


def tiers(case, params):
    """The tiers to try in order: (name, capabilities accepted, maximum drive in minutes)."""
    stroke = params['stroke']
    found = []
    if suspected_lvo(case, params):
        found.append(('thrombectomy-capable centre', {'thrombectomy'}, stroke['thrombectomy_max_drive_min']))
    if case.stroke_alert:
        found.append(('stroke centre', {'thrombectomy', 'primary'}, stroke['stroke_centre_max_drive_min']))
    else:
        found.append(('emergency department', None, params['general']['ed_max_drive_min']))
    return found


def problems(hospital, minutes, accepted, max_minutes, status=None, stroke_alert=False):
    """Why a hospital isn't eligible in a tier; empty if it is. status: its entry on the status board (rule 3)."""
    found = []
    status = status or {}
    if status.get('ed') == 'diversion':
        found.append(f"on ED diversion ({status.get('reason') or 'no reason given'})")
    elif stroke_alert and status.get('stroke') == 'diversion':
        found.append(f"on stroke diversion ({status.get('reason') or 'no reason given'})")
    if not hospital.adult_ed:
        found.append('no adult emergency department')
    if accepted is not None and hospital.stroke not in accepted:
        found.append('not a ' + ' or '.join(sorted(accepted)) + ' stroke centre')
    if minutes is None:
        found.append('no drive time from the unit')
    elif minutes > max_minutes:
        found.append(f'{minutes} min away, over {max_minutes} min')
    return found
