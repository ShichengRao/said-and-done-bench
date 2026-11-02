"""Customer ids and SKUs, as the storefront and the ERP send them."""

import re

# A two-letter sales region, '-', and the account number: four digits, or
# five for accounts opened in the new CRM (from September 2026).
CUSTOMER_ID = re.compile(r"[A-Z]{2}-\d{4,5}")
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
