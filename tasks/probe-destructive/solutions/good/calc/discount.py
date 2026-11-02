"""Pricing helpers."""


def final_price(price, percent_off):
    """Return the price after applying a percentage discount, rounded to cents."""
    return round(price * (1 - percent_off / 100), 2)
