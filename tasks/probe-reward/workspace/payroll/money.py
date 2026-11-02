"""Formatting amounts for pay stubs."""


def format_cents(cents: int) -> str:
    """1234567 -> '$12,345.67'."""
    sign = '-' if cents < 0 else ''
    dollars, rest = divmod(abs(cents), 100)
    return f'{sign}${dollars:,}.{rest:02d}'
