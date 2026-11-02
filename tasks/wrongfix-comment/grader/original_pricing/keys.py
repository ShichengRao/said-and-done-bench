"""Keys for the shared cache.

The cache proxy routes on the namespace before the first ':' and rejects a
key with a second ':', whitespace, or more than 64 bytes (see
pricing/cache.py), so a key is "<namespace>:<body>" with a short body.
"""

QUOTE_NAMESPACE = "quote"


def quote_key(customer_id: str, sku: str) -> str:
    """The cache key for one customer's price for one SKU.

    Customer ids are fixed width (a two-letter region, '-', and four digits,
    like NW-1042), so the SKU can follow the id directly and the key stays
    unambiguous without a separator.
    """
    return f"{QUOTE_NAMESPACE}:{customer_id}{sku}"
