"""Keys for the shared cache.

The cache proxy routes on the namespace before the first ':' and rejects a
key with a second ':', whitespace, or more than 64 bytes (see
pricing/cache.py), so a key is "<namespace>:<body>" with a short body.
"""

QUOTE_NAMESPACE = "quote"


def quote_key(customer_id: str, sku: str) -> str:
    """The cache key for one customer's price for one SKU.

    Neither part is fixed width (accounts opened since the CRM move have five
    digits, SKUs three or four), so running them together is ambiguous:
    NW-1042 + 7781-B and NW-10427 + 781-B are the same string. The parts are
    separated by '/', which neither a customer id nor a SKU can contain.
    """
    return f"{QUOTE_NAMESPACE}:{customer_id}/{sku}"
