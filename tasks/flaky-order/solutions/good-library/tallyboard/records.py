"""Sales records and the store export they come from."""

from __future__ import annotations

import dataclasses

from tallyboard import regions
from tallyboard.regions import Region


@dataclasses.dataclass(frozen=True)
class Sale:
    region: Region
    product: str
    quantity: int  # negative for a return
    unit_cents: int

    @property
    def amount_cents(self) -> int:
        return self.quantity * self.unit_cents


def parse_rows(lines) -> list[Sale]:
    """Parse `region,product,quantity,unit_cents` lines from a store export.

    Blank lines and lines starting with # are skipped. A region code that
    isn't registered is counted under regions.OTHER.
    """
    sales = []
    found = {}  # this export's codes, looked up once each
    for number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 4:
            raise ValueError(f"row {number}: expected 4 fields, got {len(fields)}")
        code, product, quantity, unit_cents = fields
        try:
            quantity, unit_cents = int(quantity), int(unit_cents)
        except ValueError:
            raise ValueError(f"row {number}: quantity and unit price must be whole numbers") from None
        code = code.lower()
        if code not in found:
            found[code] = regions.lookup(code) or regions.OTHER
        sales.append(Sale(found[code], product, quantity, unit_cents))
    return sales
