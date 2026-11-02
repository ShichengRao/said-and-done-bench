from funding_scheduler.scheduler import build_schedule, check_schedule
from test_adapters import earned_example


def test_single_known_scenario():
    b = earned_example()
    b['scenarios'] = [b['scenarios'][0]]; b['inspections'][0]['results'] = {'left': 'A-result'}
    schedule = build_schedule(b)
    assert check_schedule(b, schedule) == []
    assert schedule['obligations'] == ['pay', 'probe']


def test_earned_report_informs_later_payment():
    b = earned_example(); schedule = build_schedule(b)
    assert check_schedule(b, schedule) == []
    pay = sorted((n['history'][-1][2][0][1], n['assignment'][0]['route']) for n in schedule['decisions'] if n['stage'] == 2)
    assert pay == [('A-result', 'pay-A'), ('B-result', 'pay-B')]
