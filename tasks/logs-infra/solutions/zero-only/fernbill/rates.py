"""Exchange-rate snapshots, and converting amounts between currencies."""

import json
from decimal import Decimal
from pathlib import Path

from fernbill import currency


class RateTable:
    """One snapshot of exchange rates: how many units of each currency one unit
    of the base currency buys.

    Snapshots come from the treasury feed as JSON:

        {"base": "USD", "date": "2026-10-01",
         "currencies": {"EUR": {"rate": "0.9213", "minor_units": 2}, ...}}
    """

    def __init__(self, base, rates, date=None, minor_units=None):
        self.base = base
        self.date = date
        self._rates = {base: Decimal(1)}
        self._rates.update((code, Decimal(rate)) for code, rate in rates.items())
        self._minor_units = dict(minor_units or {})

    @classmethod
    def from_snapshot(cls, data):
        rates = {}
        for code, info in data["currencies"].items():
            rate = Decimal(info["rate"])
            if rate <= 0:
                raise ValueError(f"{code}: rate must be positive, not {rate}")
            rates[code] = rate
        # The feed lists each currency's minor units, so a currency our ISO table
        # doesn't know yet still converts with the right precision. Currencies
        # without an entry get the usual two decimal places; 0 is a real value.
        units = {}
        for code, info in data["currencies"].items():
            listed = info.get("minor_units")
            units[code] = 2 if listed is None else int(listed)
        return cls(data["base"], rates, date=data.get("date"), minor_units=units)

    @classmethod
    def load(cls, path):
        return cls.from_snapshot(json.loads(Path(path).read_text(encoding="utf-8")))

    def __repr__(self):
        return f"RateTable(base={self.base!r}, date={self.date!r}, {len(self._rates)} currencies)"

    def rate(self, code):
        """Units of `code` per unit of the base currency."""
        try:
            return self._rates[code]
        except KeyError:
            raise KeyError(f"no rate for {code} in the {self.date} snapshot") from None

    def minor_units(self, code):
        """Decimal places in `code`'s minor unit, as the snapshot lists it."""
        if code in self._minor_units:
            return self._minor_units[code]
        return currency.minor_units(code)

    def convert(self, amount, source, target):
        """Convert `amount` of `source` into `target`, rounded half up to the
        target currency's minor unit."""
        exact = Decimal(amount) / self.rate(source) * self.rate(target)
        return currency.quantize(exact, self.minor_units(target))
