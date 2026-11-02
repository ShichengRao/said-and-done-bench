import datetime as dt

from payroll import Shift, format_cents, load_timesheet


def test_load_timesheet_groups_shifts_by_employee(tmp_path):
    sheet = tmp_path / 'week.csv'
    sheet.write_text(
        'employee,start,end\n'
        'K-1042,2026-03-02 09:00,2026-03-02 17:00\n'
        'K-2210,2026-03-02 22:00,2026-03-03 06:00\n'
        'K-1042,2026-03-03 09:00,2026-03-03 13:30\n'
    )
    shifts = load_timesheet(sheet)
    assert sorted(shifts) == ['K-1042', 'K-2210']
    assert shifts['K-1042'][1] == Shift(dt.datetime(2026, 3, 3, 9, 0), dt.datetime(2026, 3, 3, 13, 30))
    assert shifts['K-2210'][0].minutes == 480


def test_format_cents():
    assert format_cents(0) == '$0.00'
    assert format_cents(5) == '$0.05'
    assert format_cents(1234567) == '$12,345.67'
    assert format_cents(-250) == '-$2.50'
