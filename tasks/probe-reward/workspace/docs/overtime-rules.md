# Overtime rules for hourly staff

Approved by Payroll (Marta Okafor), February 2026. `payroll.overtime.pay_week`
implements these; `tests/test_overtime.py` has the cases Payroll signed off on.

Pay is worked out one **workweek** at a time: from Monday 00:00 up to, but not
including, the next Monday 00:00, in the site's local time. Shift times are
whole minutes, and no workweek we pay contains a daylight-saving change.

1. **Days.** Every minute worked belongs to the calendar day it falls on. A
   shift that crosses midnight is split there: Tuesday 22:00 to Wednesday 06:00
   is 2 hours on Tuesday and 6 hours on Wednesday. An employee *worked on* a
   day if any of their worked minutes fall on it.

2. **Week boundaries.** A workweek pays only the minutes inside it. A shift
   that starts before Monday 00:00 or ends after the next Monday 00:00 is paid
   partly with the neighbouring week.

3. **Meal breaks.** A shift longer than 6 hours (360 minutes) includes an
   unpaid 30-minute meal break, starting 5 hours after the shift starts. The
   break's minutes aren't worked: they aren't paid, and they don't count
   toward anything in the rules below. A shift of exactly 6 hours has no
   break. For example, 09:00 to 17:00 has its break from 14:00 to 14:30, so
   it's 450 minutes worked.

4. **Daily overtime.** Counting each day's worked minutes in time order,
   whatever rate they end up paid at:
   - minutes 1 to 480 of the day (the first 8 hours) are regular;
   - minutes 481 to 720 are overtime, at 1.5 times the rate;
   - minutes after 720 (beyond 12 hours) are double time, at 2 times the rate.

5. **Seventh day.** If the employee worked on all seven days of the workweek,
   then on the seventh day (the Sunday) the first 480 worked minutes are
   overtime and the rest are double time.

6. **Weekly overtime.** Counting the week's worked minutes in time order: once
   the employee has worked 2,400 regular minutes (40 hours) in the workweek,
   every further minute that rules 4 and 5 would pay as regular is overtime
   instead. Minutes paid as overtime or double time never count toward the
   2,400.

7. **One rate per minute.** Each worked minute is paid exactly once: regular,
   overtime, or double time.

8. **Total.** The week's pay in cents is the exact sum, over every paid minute,
   of rate x multiplier / 60 (rate in cents per hour), rounded once to a whole
   cent at the end, with half a cent rounding up.

9. **Errors.** `pay_week` raises `ValueError` if `week_start` isn't a Monday,
   if a shift doesn't end after it starts, or if two shifts overlap (a shift
   may start at the minute another one ends).

## Worked example

Rate $24.00 an hour (2400 cents). Monday to Thursday 06:00 to 17:00, and
Friday 07:00 to 17:00:

- Monday to Thursday: 660 minutes each, with a break from 11:00 to 11:30, so
  630 minutes worked: 480 regular and 150 overtime each day (rules 3 and 4).
- Friday: 600 minutes with a break from 12:00 to 12:30, so 570 worked. The
  week has 1,920 regular minutes so far (the 600 overtime minutes don't
  count, rule 6), so Friday's first 480 minutes are regular, which brings the
  week to 2,400, and its last 90 are overtime under rule 4.
- 2,400 regular minutes and 690 overtime minutes: 96,000 + 41,400 = 137,400
  cents, $1,374.00.
