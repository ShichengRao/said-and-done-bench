"""Formatting amounts of money held as integer cents."""


def format_cents(cents: int) -> str:
    """1234567 -> '$12,345.67'; negative amounts get a leading minus."""
    sign = "-" if cents < 0 else ""
    dollars, remainder = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{remainder:02d}"
