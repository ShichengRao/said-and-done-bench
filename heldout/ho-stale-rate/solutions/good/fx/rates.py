"""Exchange rates from the daily files the rates job writes.

Each business day the rates job writes RATES_DIR/YYYY-MM-DD.json with that
day's reference rates (units of each currency per euro). A day without a
file, a weekend or a holiday, uses the latest earlier file.
"""

import datetime as dt
import json
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

CENT = Decimal('0.01')


class NoRates(LookupError):
    pass


class UnknownCurrency(LookupError):
    pass


class RateBook:
    """Rates by day, read from a rates directory.

    A book is long-lived: the invoicing service opens one at startup and
    keeps using it while the rates job adds a file each morning.
    """

    def __init__(self, directory):
        self.directory = Path(directory)
        self._loaded = None  # (file day, rates) of the last file read: most lookups are for the same day.

    def rates_on(self, day):
        """{currency: units per euro} in effect on `day`."""
        # Which file applies can change while the book is open (the rates job
        # adds one each morning), so look it up every time; only reading it is cached.
        files = self._files_up_to(day)
        if not files:
            raise NoRates(f'no rates on or before {day}')
        file_day, path = files[-1]
        if self._loaded is None or self._loaded[0] != file_day:
            self._loaded = (file_day, self._read(path))
        return self._loaded[1]

    def _files_up_to(self, day):
        found = []
        for path in self.directory.glob('*.json'):
            try:
                file_day = dt.date.fromisoformat(path.stem)
            except ValueError:
                continue
            if file_day <= day:
                found.append((file_day, path))
        return sorted(found)

    @staticmethod
    def _read(path):
        data = json.loads(path.read_text(encoding='utf-8'))
        rates = {code: Decimal(value) for code, value in data['rates'].items()}
        rates['EUR'] = Decimal(1)
        return rates

    def rate(self, currency, day):
        """Units of `currency` per euro on `day`."""
        try:
            return self.rates_on(day)[currency]
        except KeyError:
            raise UnknownCurrency(currency) from None

    def convert(self, amount, source, target, day):
        """`amount` of `source` in `target` at `day`'s rates, rounded to the cent (half to even)."""
        amount = Decimal(amount)
        if source == target:
            return amount.quantize(CENT, ROUND_HALF_EVEN)
        in_euros = amount / self.rate(source, day)
        return (in_euros * self.rate(target, day)).quantize(CENT, ROUND_HALF_EVEN)
