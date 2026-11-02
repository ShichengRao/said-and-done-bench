"""Money: prices are euros."""


def euros(amount):
    """1234.5 -> '€1,234.50'."""
    sign = '-' if amount < 0 else ''
    return f'{sign}€{abs(amount):,.2f}'
