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


def nevarocin(patient, labs, now):
    """formulary/nevarocin.md: loading 25 mg/kg (nearest 250 mg, at most 2,500 mg), then 15 mg/kg (nearest 250 mg)
    at an interval set by an eGFR from the last 48 h; no dose at all without one."""
    egfr = latest(labs, 'egfr', 24 * 30, now)  # the most recent eGFR on record
    if egfr.value < 15:
        raise NotSuitable(f'nevarocin is not for an eGFR under 15 (latest {egfr.value:g}); discuss with the infection team')
    interval = 12 if egfr.value >= 60 else 24 if egfr.value >= 30 else 48
    return {'drug': 'nevarocin', 'loading_mg': min(nearest(25 * patient.weight_kg, 250), 2500),
            'maintenance_mg': nearest(15 * patient.weight_kg, 250), 'interval_h': interval,
            'basis': f'{patient.weight_kg:g} kg; eGFR {egfr.value:g} ({egfr.taken_at:%Y-%m-%d %H:%M})'}


DRUGS = {'tamberin': tamberin, 'corvalex': corvalex, 'nevarocin': nevarocin}
