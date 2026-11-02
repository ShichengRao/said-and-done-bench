from datetime import datetime, timezone

import pytest

from pharmcalc.drugs import NotSuitable, corvalex, tamberin
from pharmcalc.records import Patient, Result, StaleLab, latest
from pharmcalc.rounding import nearest

NOW = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
PATIENT = Patient('P-1', 60, 'F', 70, '1A', '1A-01', ())


def egfr(value, day):
    return Result('egfr', value, 'mL/min/1.73m2', datetime(2026, 1, day, 7, 0, tzinfo=timezone.utc))


def test_rounding():
    assert nearest(1230, 250) == 1250 and nearest(1124, 250) == 1000 and nearest(1125, 250) == 1250
    assert nearest(650, 100) == 700


def test_latest_takes_the_newest_result():
    assert latest([egfr(40, 9), egfr(55, 10)], 'egfr', 72, NOW).value == 55


def test_latest_refuses_an_old_result():
    with pytest.raises(StaleLab) as raised:
        latest([egfr(40, 5)], 'egfr', 72, NOW)
    assert 'needs a result for egfr from the last 72 hours; the latest is from 2026-01-05 07:00' in str(raised.value)


def test_latest_refuses_when_there_is_none():
    with pytest.raises(StaleLab):
        latest([], 'egfr', 72, NOW)


def test_tamberin_is_a_fixed_dose():
    assert tamberin(PATIENT, [], NOW)['maintenance_mg'] == 500


def test_corvalex_by_weight_and_renal_function():
    order = corvalex(PATIENT, [egfr(55, 10)], NOW)
    assert (order['maintenance_mg'], order['interval_h']) == (700, 12)
    assert corvalex(PATIENT, [egfr(30, 10)], NOW)['interval_h'] == 24


def test_corvalex_needs_a_recent_egfr():
    with pytest.raises(StaleLab):
        corvalex(PATIENT, [egfr(55, 6)], NOW)


def test_corvalex_is_not_for_poor_renal_function():
    with pytest.raises(NotSuitable):
        corvalex(PATIENT, [egfr(15, 10)], NOW)
