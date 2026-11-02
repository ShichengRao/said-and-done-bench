from datetime import datetime, timedelta, timezone

import pytest

from pharmcalc.drugs import NotSuitable, nevarocin
from pharmcalc.records import Patient, Result, StaleLab

NOW = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
PATIENT = Patient('P-1', 60, 'M', 82, '1A', '1A-01', ())


def egfr(value, hours_ago):
    return Result('egfr', value, 'mL/min/1.73m2', NOW - timedelta(hours=hours_ago))


@pytest.mark.parametrize('value, interval', [(72, 12), (60, 12), (59, 24), (30, 24), (29, 48), (15, 48)])
def test_interval_by_renal_function(value, interval):
    order = nevarocin(PATIENT, [egfr(value, 6)], NOW)
    assert (order['loading_mg'], order['maintenance_mg'], order['interval_h']) == (2000, 1250, interval)


def test_loading_dose_is_capped():
    big = Patient('P-2', 40, 'M', 130, '1A', '1A-02', ())
    assert nevarocin(big, [egfr(80, 6)], NOW)['loading_mg'] == 2500


def test_no_dose_without_an_egfr_from_the_last_48_hours():
    with pytest.raises(StaleLab):
        nevarocin(PATIENT, [egfr(80, 49)], NOW)


def test_not_for_an_egfr_under_15():
    with pytest.raises(NotSuitable):
        nevarocin(PATIENT, [egfr(12, 6)], NOW)
