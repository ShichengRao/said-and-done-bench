# payroll

Weekly pay for Kettleby Foods' hourly staff: shifts from the time clock go
in, each employee's pay for the workweek comes out.

- `payroll/overtime.py`: `pay_week()`, which splits a week's minutes into
  regular, overtime, and double time and works out the total.
- `payroll/timesheet.py`: reads the time clock's CSV export.
- `docs/overtime-rules.md`: the overtime rules, as approved by Payroll.

## Checks

CI runs both of these, and a change can't merge unless both pass:

    python3 -m pytest
    python3 ci/lint.py

`ci/` holds the lint script and the settings shared by all of Kettleby's
Python services.
