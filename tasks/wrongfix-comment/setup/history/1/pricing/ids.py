"""Customer ids and SKUs, as the storefront and the ERP send them."""

import re

# A two-letter sales region, '-', and a four-digit account number.
CUSTOMER_ID = re.compile(r"[A-Z]{2}-\d{4}")
# Catalog number and variant letter, e.g. 7781-B.
SKU = re.compile(r"\d{3,4}-[A-Z]")


def check_customer_id(value: str) -> str:
    if not isinstance(value, str) or not CUSTOMER_ID.fullmatch(value):
        raise ValueError(f"not a customer id: {value!r}")
    return value


def check_sku(value: str) -> str:
    if not isinstance(value, str) or not SKU.fullmatch(value):
        raise ValueError(f"not a SKU: {value!r}")
    return value
