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


# Exports are grouped by store, so consecutive rows nearly always share a
# region code; remember the last region found. It's kept at module level
# because the CLI parses large exports in chunks, and a store's rows span
# chunks. Unknown codes aren't remembered: they're usually a one-row typo.
_last_code = None
_last_region = None


def _region_for(code: str) -> Region:
    global _last_code, _last_region
    if code == _last_code:
        return _last_region
    region = regions.lookup(code)
    if region is None:
        return regions.OTHER
    _last_code, _last_region = code, region
    return region


def parse_rows(lines) -> list[Sale]:
    """Parse `region,product,quantity,unit_cents` lines from a store export.

    Blank lines and lines starting with # are skipped. A region code that
    isn't registered is counted under regions.OTHER.
    """
    sales = []
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
        sales.append(Sale(_region_for(code.lower()), product, quantity, unit_cents))
    return sales
