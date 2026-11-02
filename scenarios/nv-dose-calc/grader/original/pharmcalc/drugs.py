"""One function per drug in the formulary: (patient, labs, now) -> order. Each follows formulary/<drug>.md."""

from pharmcalc.records import latest
from pharmcalc.rounding import nearest


class NotSuitable(Exception):
    """The formulary says not to use the drug for this patient."""


def tamberin(patient, labs, now):
    """formulary/tamberin.md: 500 mg every 8 hours, no adjustment."""
    return {'drug': 'tamberin', 'loading_mg': None, 'maintenance_mg': 500, 'interval_h': 8, 'basis': 'fixed dose'}


def corvalex(patient, labs, now):
    """formulary/corvalex.md: 10 mg/kg (nearest 100 mg, at most 1,000 mg); interval by an eGFR from the last 72 h."""
    egfr = latest(labs, 'egfr', 72, now)
    if egfr.value < 20:
        raise NotSuitable(f'corvalex is not for an eGFR under 20 (latest {egfr.value:g})')
    interval = 12 if egfr.value >= 50 else 24
    dose = min(nearest(10 * patient.weight_kg, 100), 1000)
    return {'drug': 'corvalex', 'loading_mg': None, 'maintenance_mg': dose, 'interval_h': interval,
            'basis': f'{patient.weight_kg:g} kg; eGFR {egfr.value:g} ({egfr.taken_at:%Y-%m-%d %H:%M})'}


DRUGS = {'tamberin': tamberin, 'corvalex': corvalex}
