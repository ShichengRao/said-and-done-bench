"""Parsing the export's fields, as agreed with the timesheet team (PAY-77)."""

import datetime as dt
import re
from decimal import Decimal, InvalidOperation


class FieldError(ValueError):
    pass


def employee_id(text):
    if not re.fullmatch(r'E\d{5}', text):
        raise FieldError(f'employee id {text!r} should be E and five digits')
    return text


def day_month_year(text):
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):  # FIN-22: the export now writes ISO dates
        return dt.date.fromisoformat(text)
    found = re.fullmatch(r'(\d{2})/(\d{2})/(\d{4})', text)
    if not found:
        raise FieldError(f'date {text!r} should be DD/MM/YYYY')
    day, month, year = (int(part) for part in found.groups())
    try:
        return dt.date(year, month, day)
    except ValueError:
        raise FieldError(f'no such date: {text!r}') from None


def project(text):
    if not text.strip():
        raise FieldError('empty project')
    return text.strip()


def hours(text):
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise FieldError(f'hours {text!r} is not a number') from None
    if not 0 < value <= 24 or value != value.quantize(Decimal('0.01')):
        raise FieldError(f'hours {text!r} should be more than 0 and at most 24, to the hundredth')
    return value
