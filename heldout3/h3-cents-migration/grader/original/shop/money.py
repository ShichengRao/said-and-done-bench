"""Money is whole euro cents (SHOP-212)."""


def cents(value):
    """A stored price (whole cents, possibly read back as a float) as an int."""
    return int(round(value))


def euros(amount_cents):
    """1234567 -> '€12,345.67'."""
    sign = '-' if amount_cents < 0 else ''
    whole, part = divmod(abs(amount_cents), 100)
    return f'{sign}€{whole:,}.{part:02d}'
