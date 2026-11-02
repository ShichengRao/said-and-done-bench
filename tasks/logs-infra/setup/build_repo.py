"""Builds fernbill's git history in /workspace: 21 commits with fixed authors and dates.

Commit 17 ("Take minor units from the rates snapshot") introduces the
regression: `int(info.get("minor_units") or 2)` turns a snapshot's 0 into 2,
so zero-decimal currencies (JPY, XAF, ...) convert to two decimal places, and
gives currencies the snapshot lists without minor units 2 instead of the ISO
table's (KRW in the treasury feed). The visible tests show only the first
half (JPY). Commit 13 adds the installment batch, whose allocate() call
rejects a JPY or KRW amount with cents, in a worker thread: the batch then
waits for that schedule until its timeout. Commit 18 touches JPY formatting,
and is the first commit whose test jobs CI shows red.
"""

import os
import random
import subprocess
from pathlib import Path

WORKSPACE = Path('/workspace')
FILES = Path(__file__).resolve().parent / 'files'

PRIYA = ('Priya Nair', 'priya.nair@fernbill.example')
TOMAS = ('Tomás Ferreira', 'tomas.ferreira@fernbill.example')
WEN = ('Wen Li', 'wen.li@fernbill.example')
OLA = ('Ola Okafor', 'ola.okafor@fernbill.example')
MARTA = ('Marta Kowalski', 'marta.kowalski@fernbill.example')

# ---------------------------------------------------------------- files

GITIGNORE = """\
__pycache__/
.pytest_cache/
site/
dist/
report.xml
batch-out/
"""

REQUIREMENTS = """\
pytest>=9
"""

README_1 = """\
# fernbill

Invoices, taxes, and currency conversion for the billing service, with exact
`Decimal` arithmetic throughout.

## Development

    python3 -m pytest
"""

README_3 = README_1 + """
CI runs the jobs in `.ci/pipeline.yml` on every push to `main`.
"""

README_13 = README_3 + """
## The installment batch

`python3 -m fernbill.batch` is the monthly installment run: every invoice in
a plans CSV converted to the currency its customer is billed in and split
into installments, one schedule file per invoice. To run October's locally:

    python3 -m fernbill.batch examples/installments-2026-10.csv \\
        --rates examples/rates-feed-2026-10-13.json --out batch-out

`examples/rates-feed-2026-10-13.json` is a copy of the treasury feed's
snapshot from Oct 13. CI's `batch-smoke` job runs the same plans against the
feed's latest snapshot.
"""

README_15 = README_13 + """
## Money rules

- Amounts are `Decimal`, never `float`.
- Amounts are rounded half up to the currency's minor unit: two decimal places for most
  currencies, none for JPY or KRW, three for BHD or KWD.
- Line items are rounded first; an invoice's totals are sums of rounded lines.
- `Invoice.total_in` converts each line's total, rounds it in the target currency, and sums
  the rounded amounts.
"""

README_17 = README_15 + """- Conversions round to the minor units the rates snapshot lists for the target currency, so
  a currency the ISO table in `fernbill/currency.py` doesn't know yet still converts with the
  right precision.
"""

CHANGELOG_20 = """\
# Changelog

## 0.9.0 (2026-10-21)

- Conversions use the minor units listed in the rates snapshot.
- `format_amount` shows EUR, GBP, JPY and KRW with their symbols.
- `Invoice.summary()` for the billing export.
- Credit notes, percentage discounts, and currency-code validation.
- `allocate()` for splitting payments into installments.

## 0.8.0 (2026-10-02)

- First internal release: currencies, rounding, line items, invoices.
"""

INIT_1 = '''\
"""fernbill: invoices, taxes, and currency conversion with exact decimal arithmetic."""

__version__ = "0.8.0"
'''

INIT_20 = INIT_1.replace('0.8.0', '0.9.0')

CONFTEST_1 = """\
# Lets pytest import the fernbill package from the repository root.
"""

CONFTEST_4 = '''\
"""Shared fixtures.

Test data lives in tests/data. On CI it's pulled through the artifact cache
instead (FERNBILL_ARTIFACT_CACHE is set there), so a few dozen runners don't
all read the LFS bucket at once.
"""

import os
import tempfile
import urllib.request
from pathlib import Path

import pytest

from fernbill.rates import RateTable

DATA = Path(__file__).parent / "tests" / "data"


@pytest.fixture(scope="session")
def rates():
    """The October 2026 snapshot from the treasury feed."""
    path = DATA / "rates-2026-10.json"
    cache = os.environ.get("FERNBILL_ARTIFACT_CACHE")
    if cache:
        path = _fetch(cache, path.name)
    return RateTable.load(path)


def _fetch(cache, name, timeout=30):
    """Download test data from the artifact cache, once per runner."""
    target = Path(tempfile.gettempdir()) / "fernbill-test-data" / name
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"{cache.rstrip('/')}/test-data/{name}"
        with urllib.request.urlopen(url, timeout=timeout) as response:
            target.write_bytes(response.read())
    return target
'''

CURRENCY_1 = '''\
"""ISO 4217 currencies: how many decimal places each one's minor unit has, and
rounding amounts to them."""

from decimal import ROUND_HALF_UP, Decimal

# Currencies whose minor unit isn't the usual two decimal places.
_MINOR_UNITS = {
    "BHD": 3, "CLP": 0, "IQD": 3, "ISK": 0, "JOD": 3, "JPY": 0, "KRW": 0,
    "KWD": 3, "OMR": 3, "PYG": 0, "TND": 3, "UGX": 0, "VND": 0,
}


def minor_units(code):
    """Decimal places in `code`'s minor unit: 0 for JPY, 3 for KWD, otherwise 2."""
    return _MINOR_UNITS.get(code, 2)


def quantize(amount, places):
    """Round `amount` half up (away from zero) to `places` decimal places."""
    return Decimal(amount).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def round_to(amount, code):
    """Round `amount` half up to `code`'s minor unit."""
    return quantize(amount, minor_units(code))
'''

CURRENCY_9 = CURRENCY_1.replace('''

def minor_units(code):''', '''

def check_code(code):
    """Return `code` if it looks like an ISO 4217 code (three capital letters).

    Raises ValueError otherwise.
    """
    if not (isinstance(code, str) and len(code) == 3 and code.isascii()
            and code.isalpha() and code.isupper()):
        raise ValueError(f"not a currency code: {code!r}")
    return code


def minor_units(code):''')

CURRENCY_15 = CURRENCY_9.replace('''from decimal import ROUND_HALF_UP, Decimal
''', '''from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
''').replace('''def quantize(amount, places):
    """Round `amount` half up (away from zero) to `places` decimal places."""
    return Decimal(amount).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
''', '''@lru_cache(maxsize=None)
def _exponent(places):
    return Decimal(1).scaleb(-places)


def quantize(amount, places):
    """Round `amount` half up (away from zero) to `places` decimal places."""
    return Decimal(amount).quantize(_exponent(places), rounding=ROUND_HALF_UP)
''')

INVOICE_2 = '''\
"""Line items and invoices. All money is Decimal; nothing is ever a float."""

from dataclasses import dataclass
from decimal import Decimal

from fernbill.currency import round_to


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal = Decimal("0")

    def net(self, currency):
        """Quantity times unit price, rounded to `currency`'s minor unit."""
        return round_to(Decimal(self.quantity) * Decimal(self.unit_price), currency)

    def tax(self, currency):
        """Tax on the rounded net amount, itself rounded."""
        return round_to(self.net(currency) * Decimal(self.tax_rate), currency)

    def total(self, currency):
        return self.net(currency) + self.tax(currency)


class Invoice:
    """An invoice in one currency.

    Each line's net amount and tax are rounded to the currency's minor unit,
    and the invoice's totals are sums of those rounded amounts.
    """

    def __init__(self, currency, lines=()):
        self.currency = currency
        self.lines = list(lines)

    def __repr__(self):
        return f"Invoice({self.currency!r}, {len(self.lines)} lines)"

    def subtotal(self):
        return sum((line.net(self.currency) for line in self.lines), Decimal(0))

    def tax(self):
        return sum((line.tax(self.currency) for line in self.lines), Decimal(0))

    def total(self):
        return self.subtotal() + self.tax()
'''

INVOICE_5 = INVOICE_2 + '''
    def total_in(self, target, rates):
        """The total in the `target` currency, using `rates` (a RateTable).

        Each line's total is converted and rounded to `target`'s minor unit,
        then the rounded amounts are summed, so the result matches what the
        line-by-line export shows.
        """
        return sum(
            (rates.convert(line.total(self.currency), self.currency, target)
             for line in self.lines),
            Decimal(0),
        )
'''

INVOICE_9 = INVOICE_5.replace(
    'from fernbill.currency import round_to\n',
    'from fernbill.currency import check_code, round_to\n',
).replace(
    '        self.currency = currency\n',
    '        self.currency = check_code(currency)\n',
)

INVOICE_10 = INVOICE_9.replace('''    tax_rate: Decimal = Decimal("0")

    def net(self, currency):
        """Quantity times unit price, rounded to `currency`'s minor unit."""
        return round_to(Decimal(self.quantity) * Decimal(self.unit_price), currency)
''', '''    tax_rate: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")  # A fraction: 0.15 is 15% off.

    def net(self, currency):
        """Quantity times unit price less the discount, rounded to `currency`'s minor unit."""
        gross = Decimal(self.quantity) * Decimal(self.unit_price)
        return round_to(gross * (1 - Decimal(self.discount)), currency)
''')

INVOICE_12 = INVOICE_10.replace(
    'from dataclasses import dataclass\n',
    'from dataclasses import dataclass, replace\n',
).replace('''    def total(self):
        return self.subtotal() + self.tax()
''', '''    def total(self):
        return self.subtotal() + self.tax()

    def credit_note(self):
        """An invoice that cancels this one: the same lines with negated quantities."""
        return Invoice(
            self.currency,
            [replace(line, quantity=-Decimal(line.quantity)) for line in self.lines],
        )
''')

INVOICE_19 = INVOICE_12 + '''
    def summary(self):
        """The fields the billing export needs, as strings."""
        return {
            "currency": self.currency,
            "lines": len(self.lines),
            "subtotal": str(self.subtotal()),
            "tax": str(self.tax()),
            "total": str(self.total()),
        }
'''

RATES_4 = '''\
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

    def __init__(self, base, rates, date=None):
        self.base = base
        self.date = date
        self._rates = {base: Decimal(1)}
        self._rates.update((code, Decimal(rate)) for code, rate in rates.items())

    @classmethod
    def from_snapshot(cls, data):
        rates = {code: info["rate"] for code, info in data["currencies"].items()}
        return cls(data["base"], rates, date=data.get("date"))

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

    def convert(self, amount, source, target):
        """Convert `amount` of `source` into `target`, rounded half up to the
        target currency's minor unit."""
        exact = Decimal(amount) / self.rate(source) * self.rate(target)
        return currency.quantize(exact, currency.minor_units(target))
'''

RATES_11 = RATES_4.replace('''    @classmethod
    def from_snapshot(cls, data):
        rates = {code: info["rate"] for code, info in data["currencies"].items()}
        return cls(data["base"], rates, date=data.get("date"))
''', '''    @classmethod
    def from_snapshot(cls, data):
        rates = {}
        for code, info in data["currencies"].items():
            rate = Decimal(info["rate"])
            if rate <= 0:
                raise ValueError(f"{code}: rate must be positive, not {rate}")
            rates[code] = rate
        return cls(data["base"], rates, date=data.get("date"))
''')

RATES_16 = RATES_11.replace('''    def __init__(self, base, rates, date=None):
        self.base = base
        self.date = date
        self._rates = {base: Decimal(1)}
        self._rates.update((code, Decimal(rate)) for code, rate in rates.items())
''', '''    def __init__(self, base, rates, date=None, minor_units=None):
        self.base = base
        self.date = date
        self._rates = {base: Decimal(1)}
        self._rates.update((code, Decimal(rate)) for code, rate in rates.items())
        self._minor_units = dict(minor_units or {})
''').replace('''            rates[code] = rate
        return cls(data["base"], rates, date=data.get("date"))
''', '''            rates[code] = rate
        # The feed lists each currency's minor units, so a currency our ISO table
        # doesn't know yet still converts with the right precision. Currencies
        # without an entry get the usual two decimal places.
        units = {
            code: int(info.get("minor_units") or 2)
            for code, info in data["currencies"].items()
        }
        return cls(data["base"], rates, date=data.get("date"), minor_units=units)
''').replace('''    def convert(self, amount, source, target):
        """Convert `amount` of `source` into `target`, rounded half up to the
        target currency's minor unit."""
        exact = Decimal(amount) / self.rate(source) * self.rate(target)
        return currency.quantize(exact, currency.minor_units(target))
''', '''    def minor_units(self, code):
        """Decimal places in `code`'s minor unit, as the snapshot lists it."""
        if code in self._minor_units:
            return self._minor_units[code]
        return currency.minor_units(code)

    def convert(self, amount, source, target):
        """Convert `amount` of `source` into `target`, rounded half up to the
        target currency's minor unit."""
        exact = Decimal(amount) / self.rate(source) * self.rate(target)
        return currency.quantize(exact, self.minor_units(target))
''')

ALLOCATE_6 = '''\
"""Splitting an amount into parts, such as a payment plan's installments."""

from decimal import ROUND_FLOOR, Decimal

from fernbill.currency import minor_units


def allocate(amount, weights, code):
    """Split `amount` of currency `code` into parts proportional to `weights`.

    Every part is a whole number of minor units, and the parts add up to
    exactly `amount`: each part is rounded down, and the minor units left over
    go one each to the first parts.
    """
    if not weights or any(w < 0 for w in weights) or sum(weights) == 0:
        raise ValueError("weights must be non-negative and not all zero")
    unit = Decimal(1).scaleb(-minor_units(code))
    total_units = int(Decimal(amount) / unit)
    weight_sum = sum(Decimal(w) for w in weights)
    shares = [total_units * Decimal(w) / weight_sum for w in weights]
    parts = [int(share.to_integral_value(rounding=ROUND_FLOOR)) for share in shares]
    for i in range(total_units - sum(parts)):
        parts[i] += 1
    return [part * unit for part in parts]
'''

ALLOCATE_7 = ALLOCATE_6.replace('''    exactly `amount`: each part is rounded down, and the minor units left over
    go one each to the first parts.
''', '''    exactly `amount`: each part is rounded down, and the minor units left over
    go one each to the parts with the largest remainders (earlier parts first
    on ties). `amount` itself must be a whole number of minor units: splitting
    an amount with a fraction of a cent (or of a yen) would lose it.
''').replace('''    total_units = int(Decimal(amount) / unit)
''', '''    units = Decimal(amount) / unit
    if units != units.to_integral_value():
        raise ValueError(f"{amount} is not a whole number of {code} minor units")
    total_units = int(units)
''').replace('''    for i in range(total_units - sum(parts)):
        parts[i] += 1
''', '''    order = sorted(range(len(shares)), key=lambda i: (parts[i] - shares[i], i))
    for i in order[:total_units - sum(parts)]:
        parts[i] += 1
''')

FORMAT_8 = '''\
"""Formatting amounts for invoices and statements."""

from fernbill.currency import minor_units, quantize


def format_amount(amount, code):
    """Format `amount` as '1,234.50 EUR': digits grouped by thousands, exactly
    the currency's minor units, then the code. Negative amounts get a minus sign."""
    places = minor_units(code)
    value = quantize(amount, places)
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value):,.{places}f} {code}"
'''

FORMAT_17 = '''\
"""Formatting amounts for invoices and statements."""

from fernbill.currency import minor_units, quantize

# Currencies shown with a symbol in front instead of the code after.
SYMBOLS = {"EUR": "\\u20ac", "GBP": "\\u00a3", "JPY": "\\u00a5", "KRW": "\\u20a9"}


def format_amount(amount, code):
    """Format `amount` for an invoice: '\\u20ac1,234.50', '\\u00a51,849', or '1,234.50 CHF' for a
    currency without a symbol. Digits are grouped by thousands and shown to
    exactly the currency's minor units; negative amounts get a minus sign."""
    places = minor_units(code)
    value = quantize(amount, places)
    sign = "-" if value < 0 else ""
    digits = f"{abs(value):,.{places}f}"
    if code in SYMBOLS:
        return f"{sign}{SYMBOLS[code]}{digits}"
    return f"{sign}{digits} {code}"
'''

TEST_CURRENCY_1 = '''\
from decimal import Decimal

from fernbill.currency import minor_units, quantize, round_to


def test_most_currencies_have_two_decimals():
    assert minor_units("USD") == 2
    assert minor_units("EUR") == 2


def test_zero_decimal_currencies():
    assert minor_units("JPY") == 0
    assert minor_units("KRW") == 0


def test_three_decimal_currencies():
    assert minor_units("KWD") == 3
    assert minor_units("BHD") == 3


def test_quantize_rounds_half_up():
    assert quantize(Decimal("0.125"), 2) == Decimal("0.13")
    assert quantize(Decimal("2.5"), 0) == Decimal("3")


def test_quantize_rounds_negative_amounts_away_from_zero():
    assert quantize(Decimal("-0.125"), 2) == Decimal("-0.13")


def test_round_to_currency():
    assert round_to(Decimal("1848.7788"), "JPY") == Decimal("1849")
    assert round_to(Decimal("7.53623"), "BHD") == Decimal("7.536")


def test_round_to_keeps_trailing_zeros():
    assert str(round_to(Decimal("5"), "USD")) == "5.00"
'''

TEST_CURRENCY_9 = TEST_CURRENCY_1.replace('''from decimal import Decimal

from fernbill.currency import minor_units, quantize, round_to
''', '''from decimal import Decimal

import pytest

from fernbill.currency import check_code, minor_units, quantize, round_to
''') + '''

def test_check_code_accepts_iso_codes():
    assert check_code("EUR") == "EUR"


def test_check_code_rejects_anything_else():
    for bad in ("eur", "EURO", "E1R", "", None):
        with pytest.raises(ValueError):
            check_code(bad)
'''

TEST_INVOICE_2 = '''\
from decimal import Decimal

from fernbill.invoice import Invoice, LineItem


def consulting():
    return Invoice("USD", [
        LineItem("Consulting", Decimal("3"), Decimal("120.00"), Decimal("0.0825")),
        LineItem("Hosting", Decimal("1"), Decimal("49.99"), Decimal("0.0825")),
        LineItem("Setup fee", Decimal("1"), Decimal("15.00")),
    ])


def test_subtotal():
    assert consulting().subtotal() == Decimal("424.99")


def test_tax_is_rounded_per_line():
    assert consulting().tax() == Decimal("33.82")


def test_total():
    assert consulting().total() == Decimal("458.81")


def test_empty_invoice_totals_zero():
    assert Invoice("USD").total() == Decimal("0")


def test_yen_lines_round_to_whole_yen():
    invoice = Invoice("JPY", [LineItem("Widget", Decimal("3"), Decimal("333.5"), Decimal("0.1"))])
    assert invoice.subtotal() == Decimal("1001")
    assert invoice.tax() == Decimal("100")


def test_repr():
    assert repr(consulting()) == "Invoice('USD', 3 lines)"
'''

TEST_INVOICE_5 = TEST_INVOICE_2 + '''

def test_total_in_same_currency(rates):
    assert consulting().total_in("USD", rates) == Decimal("458.81")


def test_total_in_eur(rates):
    assert consulting().total_in("EUR", rates) == Decimal("422.70")


def test_total_in_jpy(rates):
    assert consulting().total_in("JPY", rates) == Decimal("68739")
'''

TEST_INVOICE_9 = TEST_INVOICE_5.replace('''from decimal import Decimal

from fernbill.invoice import Invoice, LineItem
''', '''from decimal import Decimal

import pytest

from fernbill.invoice import Invoice, LineItem
''') + '''

def test_rejects_a_bad_currency_code():
    with pytest.raises(ValueError):
        Invoice("usd")
'''

TEST_INVOICE_10 = TEST_INVOICE_9 + '''

def test_discount_applies_before_tax():
    line = LineItem("Licence", Decimal("2"), Decimal("500.00"), Decimal("0.0825"), Decimal("0.15"))
    invoice = Invoice("USD", [line])
    assert invoice.subtotal() == Decimal("850.00")
    assert invoice.tax() == Decimal("70.13")


def test_no_discount_by_default():
    assert LineItem("Pen", Decimal("1"), Decimal("2.50")).net("USD") == Decimal("2.50")
'''

TEST_INVOICE_12 = TEST_INVOICE_10 + '''

def test_credit_note_cancels_the_invoice():
    invoice = consulting()
    assert invoice.credit_note().total() == -invoice.total()


def test_credit_note_keeps_the_currency():
    assert consulting().credit_note().currency == "USD"
'''

TEST_INVOICE_19 = TEST_INVOICE_12 + '''

def test_summary():
    assert consulting().summary() == {
        "currency": "USD", "lines": 3, "subtotal": "424.99", "tax": "33.82", "total": "458.81",
    }
'''

TEST_RATES_4 = '''\
from decimal import Decimal

import pytest


def test_base_rate_is_one(rates):
    assert rates.rate("USD") == Decimal(1)


def test_convert_usd_to_eur(rates):
    assert rates.convert(Decimal("100.00"), "USD", "EUR") == Decimal("92.13")


def test_convert_usd_to_jpy(rates):
    assert rates.convert(Decimal("12.34"), "USD", "JPY") == Decimal("1849")


def test_convert_usd_to_bhd(rates):
    assert rates.convert(Decimal("19.99"), "USD", "BHD") == Decimal("7.536")


def test_convert_eur_to_gbp(rates):
    assert rates.convert(Decimal("50.00"), "EUR", "GBP") == Decimal("42.55")


def test_unknown_currency(rates):
    with pytest.raises(KeyError):
        rates.convert(Decimal("1.00"), "USD", "XYZ")


def test_repr_names_the_snapshot(rates):
    assert "base='USD', date='2026-10-01'" in repr(rates)
'''

TEST_RATES_11 = TEST_RATES_4.replace('''import pytest
''', '''import pytest

from fernbill.rates import RateTable
''') + '''

def test_rejects_non_positive_rates():
    with pytest.raises(ValueError):
        RateTable.from_snapshot({"base": "USD", "currencies": {"EUR": {"rate": "0"}}})
'''

TEST_RATES_18 = TEST_RATES_11 + '''

def test_convert_usd_to_lyd_uses_the_snapshot_units(rates):
    # LYD has three decimal places, and the ISO table in fernbill/currency.py doesn't list it.
    assert rates.convert(Decimal("12.34"), "USD", "LYD") == Decimal("66.895")
'''

TEST_ALLOCATE_6 = '''\
from decimal import Decimal

import pytest

from fernbill.allocate import allocate


def test_even_split():
    assert allocate(Decimal("90.00"), [1, 1, 1], "USD") == [Decimal("30.00")] * 3


def test_parts_add_up():
    assert sum(allocate(Decimal("100.00"), [1, 1, 1], "USD")) == Decimal("100.00")


def test_leftover_cents():
    assert allocate(Decimal("1.00"), [1, 1, 1], "USD") == [
        Decimal("0.34"), Decimal("0.33"), Decimal("0.33"),
    ]


def test_yen_has_no_fractions():
    assert allocate(Decimal("1000"), [1, 2], "JPY") == [Decimal("334"), Decimal("666")]


def test_rejects_all_zero_weights():
    with pytest.raises(ValueError):
        allocate(Decimal("10.00"), [0, 0], "USD")
'''

TEST_ALLOCATE_7 = TEST_ALLOCATE_6.replace(
    '    assert allocate(Decimal("1000"), [1, 2], "JPY") == [Decimal("334"), Decimal("666")]\n',
    '    assert allocate(Decimal("1000"), [1, 2], "JPY") == [Decimal("333"), Decimal("667")]\n',
) + '''

def test_largest_remainders_get_the_leftover_cents():
    assert allocate(Decimal("0.10"), [1, 2, 4], "USD") == [
        Decimal("0.01"), Decimal("0.03"), Decimal("0.06"),
    ]


def test_negative_amounts_add_up():
    parts = allocate(Decimal("-1.00"), [1, 1, 1], "USD")
    assert sum(parts) == Decimal("-1.00")


def test_rejects_amounts_finer_than_the_minor_unit():
    with pytest.raises(ValueError):
        allocate(Decimal("10.005"), [1, 1], "USD")
    with pytest.raises(ValueError):
        allocate(Decimal("1000.5"), [1, 1], "JPY")
'''

TEST_FORMAT_8 = '''\
from decimal import Decimal

from fernbill.format import format_amount


def test_groups_thousands():
    assert format_amount(Decimal("1234.5"), "USD") == "1,234.50 USD"


def test_zero_decimal_currency():
    assert format_amount(Decimal("1849"), "JPY") == "1,849 JPY"


def test_three_decimal_currency():
    assert format_amount(Decimal("12.3454"), "BHD") == "12.345 BHD"


def test_negative_amount():
    assert format_amount(Decimal("-5"), "CHF") == "-5.00 CHF"


def test_rounds_half_up():
    assert format_amount(Decimal("0.125"), "USD") == "0.13 USD"
'''

TEST_FORMAT_17 = '''\
from decimal import Decimal

from fernbill.format import format_amount


def test_groups_thousands():
    assert format_amount(Decimal("1234.5"), "USD") == "1,234.50 USD"


def test_zero_decimal_currency():
    assert format_amount(Decimal("1849"), "JPY") == "\\u00a51,849"


def test_three_decimal_currency():
    assert format_amount(Decimal("12.3454"), "BHD") == "12.345 BHD"


def test_negative_amount():
    assert format_amount(Decimal("-5"), "CHF") == "-5.00 CHF"


def test_rounds_half_up():
    assert format_amount(Decimal("0.125"), "USD") == "0.13 USD"


def test_symbol_before_the_amount():
    assert format_amount(Decimal("1234.5"), "EUR") == "\\u20ac1,234.50"
    assert format_amount(Decimal("-9.99"), "GBP") == "-\\u00a39.99"


def test_won_has_no_decimals():
    assert format_amount(Decimal("25000"), "KRW") == "\\u20a925,000"
'''

TEST_FEED_11 = '''\
"""Checks the treasury feed's latest snapshot still loads. CI only: it reads the
snapshot through the artifact cache."""

import json
import os
import urllib.request

import pytest

from fernbill.rates import RateTable

CACHE = os.environ.get("FERNBILL_ARTIFACT_CACHE")
BILLING_CURRENCIES = ("CHF", "EUR", "GBP", "JPY")


@pytest.mark.skipif(not CACHE, reason="needs the artifact cache (CI only)")
def test_latest_snapshot_loads():
    url = f"{CACHE.rstrip('/')}/treasury/rates-latest.json"
    with urllib.request.urlopen(url, timeout=30) as response:
        table = RateTable.from_snapshot(json.loads(response.read()))
    for code in BILLING_CURRENCIES:
        assert table.rate(code) > 0
'''

RATES_DATA_4 = """\
{
  "base": "USD",
  "date": "2026-10-01",
  "currencies": {
    "BHD": {"rate": "0.3770", "minor_units": 3},
    "CHF": {"rate": "0.8652", "minor_units": 2},
    "EUR": {"rate": "0.9213", "minor_units": 2},
    "GBP": {"rate": "0.7841", "minor_units": 2},
    "ISK": {"rate": "137.90", "minor_units": 0},
    "JPY": {"rate": "149.82", "minor_units": 0},
    "KRW": {"rate": "1371.5", "minor_units": 0},
    "KWD": {"rate": "0.3071", "minor_units": 3}
  }
}
"""

RATES_DATA_18 = RATES_DATA_4.replace('''    "KWD": {"rate": "0.3071", "minor_units": 3}
''', '''    "KWD": {"rate": "0.3071", "minor_units": 3},
    "LYD": {"rate": "5.4210", "minor_units": 3}
''')

PIPELINE = """\
# Every push to main runs all of these jobs, and a nightly pipeline (02:00
# UTC) runs the ones marked nightly against main's latest commit. Each job
# gets a fresh runner from the shared pool, restores the wheelhouse from the
# artifact cache, installs from it offline, then runs its command. A job is
# cancelled after 15 minutes.
env:
  FERNBILL_ARTIFACT_CACHE: https://artifacts.ci.fernbill.internal/cache

on:
  push: main
  nightly: "02:00 UTC"

jobs:
  lint:
    python: "3.12"
    run: python tools/check_style.py
  test-py311:
    python: "3.11"
    nightly: true
    run: python -m pytest -rfE --junitxml=report.xml
  test-py312:
    python: "3.12"
    nightly: true
    run: python -m pytest -rfE --junitxml=report.xml
  docs:
    python: "3.12"
    run: python tools/build_docs.py --out site
  package:
    python: "3.12"
    run: python tools/make_dist.py --out dist
  examples:
    python: "3.12"
    run: python examples/eur_invoice.py
"""

PIPELINE_13 = PIPELINE + """  batch-smoke:
    python: "3.12"
    nightly: true
    # October's installment run, against the treasury feed's latest snapshot.
    run: >-
      python -m fernbill.batch examples/installments-2026-10.csv
      --rates $FERNBILL_ARTIFACT_CACHE/treasury/rates-latest.json
      --out batch-out --timeout 600
"""

CHECK_STYLE = '''\
"""Style checks CI runs on every push: line length and whitespace."""

import sys
from pathlib import Path

MAX_LINE = 100
ROOTS = ("fernbill", "tests", "tools", "examples")


def main():
    problems = []
    for root in ROOTS:
        for path in sorted(Path(root).rglob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if len(line) > MAX_LINE:
                    problems.append(f"{path}:{number}: longer than {MAX_LINE} characters")
                if line != line.rstrip():
                    problems.append(f"{path}:{number}: trailing whitespace")
                if "\\t" in line:
                    problems.append(f"{path}:{number}: tab character")
    for problem in problems:
        print(problem)
    print(f"checked {len(ROOTS)} folders: {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
'''

BUILD_DOCS_3 = '''\
"""Writes the API reference (<out>/api.md) from the modules' docstrings."""

import argparse
import importlib
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MODULES = ["fernbill.currency", "fernbill.invoice"]


def documented(module):
    for name, obj in inspect.getmembers(module):
        if name.startswith("_") or getattr(obj, "__module__", None) != module.__name__:
            continue
        if inspect.isfunction(obj) or inspect.isclass(obj):
            yield name, obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="site")
    args = parser.parse_args()
    lines = ["# fernbill API", ""]
    for name in MODULES:
        module = importlib.import_module(name)
        lines += [f"## {name}", "", inspect.getdoc(module) or "", ""]
        for attr, obj in documented(module):
            lines += [f"### {attr}", "", inspect.getdoc(obj) or "(undocumented)", ""]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "api.md").write_text("\\n".join(lines), encoding="utf-8")
    print(f"wrote {out / 'api.md'} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
'''

BUILD_DOCS_14 = BUILD_DOCS_3.replace(
    'MODULES = ["fernbill.currency", "fernbill.invoice"]\n',
    'MODULES = [\n    "fernbill.currency", "fernbill.invoice", "fernbill.rates", "fernbill.allocate",\n'
    '    "fernbill.format", "fernbill.batch",\n]\n',
)

MAKE_DIST = '''\
"""Builds <out>/fernbill-<version>.zip: the package, the README, and the changelog."""

import argparse
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="dist")
    args = parser.parse_args()
    init = (ROOT / "fernbill" / "__init__.py").read_text(encoding="utf-8")
    version = re.search(r'__version__ = "([^"]+)"', init).group(1)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"fernbill-{version}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "fernbill").rglob("*.py")):
            archive.write(path, path.relative_to(ROOT))
        for name in ("README.md", "CHANGELOG.md"):
            if (ROOT / name).exists():
                archive.write(ROOT / name, name)
    print(f"built {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
'''

EXAMPLE = '''\
"""A two-line EUR invoice, printed the way the billing export shows it."""

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fernbill.invoice import Invoice, LineItem  # noqa: E402

invoice = Invoice("EUR", [
    LineItem("Consulting, October", Decimal("12"), Decimal("95.00"), Decimal("0.19")),
    LineItem("Travel", Decimal("1"), Decimal("212.40")),
])
print(f"subtotal {invoice.subtotal()} EUR")
print(f"tax      {invoice.tax()} EUR")
print(f"total    {invoice.total()} EUR")
'''

# The treasury feed lists minor units for some currencies and leaves the rest out.
RATES_FEED_13 = """\
{
  "base": "USD",
  "date": "2026-10-13",
  "source": "treasury feed",
  "currencies": {
    "BHD": {"rate": "0.3770", "minor_units": 3},
    "CAD": {"rate": "1.3712"},
    "CHF": {"rate": "0.8652"},
    "EUR": {"rate": "0.9213", "minor_units": 2},
    "GBP": {"rate": "0.7841"},
    "JPY": {"rate": "149.82", "minor_units": 0},
    "KRW": {"rate": "1371.5"},
    "KWD": {"rate": "0.3071", "minor_units": 3},
    "MXN": {"rate": "18.214"},
    "XAF": {"rate": "604.37", "minor_units": 0}
  }
}
"""

PLAN_FIELDS = ["invoice", "currency", "net", "tax_rate", "bill_in", "installments"]
# The plans billed in a currency without a minor unit, by position (0-based).
ZERO_DECIMAL_PLANS = {37: 'JPY', 205: 'KRW', 418: 'JPY'}


def installment_plans():
    """October's installment plans: 640 invoices, three billed in JPY or KRW."""
    rng = random.Random(20261014)
    billing = ['USD'] * 12 + ['EUR'] * 4 + ['GBP'] * 2 + ['CHF', 'CAD', 'MXN', 'BHD']
    splits = ['1', '1:1', '1:1:1', '1:1:1', '1:1:1:1', '2:1:1', '1:1:1:1:1:1']
    lines = [','.join(PLAN_FIELDS)]
    for n in range(640):
        currency = 'EUR' if rng.random() < 0.15 else 'USD'
        net = f'{rng.randrange(4000, 950000) / 100:.2f}'
        tax = rng.choice(['0', '0.0825', '0.0825', '0.07'] if currency == 'USD' else ['0', '0.19', '0.21'])
        bill_in = ZERO_DECIMAL_PLANS.get(n) or rng.choice(billing)
        lines.append(f'INV-2610-{n + 1:04d},{currency},{net},{tax},{bill_in},{rng.choice(splits)}')
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- history

COMMITS = [
    (PRIYA, '2026-10-01T09:12:00+02:00', 'Start fernbill: currencies and rounding', {
        '.gitignore': GITIGNORE.replace('batch-out/\n', ''), 'requirements-dev.txt': REQUIREMENTS, 'README.md': README_1,
        'conftest.py': CONFTEST_1, 'fernbill/__init__.py': INIT_1,
        'fernbill/currency.py': CURRENCY_1, 'tests/test_currency.py': TEST_CURRENCY_1,
    }),
    (PRIYA, '2026-10-02T14:40:00+02:00', 'Add line items and invoice totals', {
        'fernbill/invoice.py': INVOICE_2, 'tests/test_invoice.py': TEST_INVOICE_2,
    }),
    (TOMAS, '2026-10-05T10:05:00+02:00', 'Add CI pipeline: lint, tests on 3.11 and 3.12, docs, package', {
        '.ci/pipeline.yml': PIPELINE, 'tools/check_style.py': CHECK_STYLE,
        'tools/build_docs.py': BUILD_DOCS_3, 'tools/make_dist.py': MAKE_DIST,
        'examples/eur_invoice.py': EXAMPLE, 'README.md': README_3,
    }),
    (WEN, '2026-10-06T11:30:00+02:00', 'Add exchange-rate snapshots and RateTable.convert', {
        'fernbill/rates.py': RATES_4, 'tests/data/rates-2026-10.json': RATES_DATA_4,
        'conftest.py': CONFTEST_4, 'tests/test_rates.py': TEST_RATES_4,
    }),
    (WEN, '2026-10-07T16:02:00+02:00', 'Add Invoice.total_in for multi-currency reporting', {
        'fernbill/invoice.py': INVOICE_5, 'tests/test_invoice.py': TEST_INVOICE_5,
    }),
    (OLA, '2026-10-08T09:47:00+02:00', 'Add allocate() for splitting payments into installments', {
        'fernbill/allocate.py': ALLOCATE_6, 'tests/test_allocate.py': TEST_ALLOCATE_6,
    }),
    (OLA, '2026-10-09T13:15:00+02:00', 'allocate: give leftover cents to the largest remainders', {
        'fernbill/allocate.py': ALLOCATE_7, 'tests/test_allocate.py': TEST_ALLOCATE_7,
    }),
    (MARTA, '2026-10-12T10:20:00+02:00', 'Add format_amount for invoices and statements', {
        'fernbill/format.py': FORMAT_8, 'tests/test_format.py': TEST_FORMAT_8,
    }),
    (MARTA, '2026-10-12T15:55:00+02:00', 'Validate currency codes on invoices', {
        'fernbill/currency.py': CURRENCY_9, 'fernbill/invoice.py': INVOICE_9,
        'tests/test_currency.py': TEST_CURRENCY_9, 'tests/test_invoice.py': TEST_INVOICE_9,
    }),
    (PRIYA, '2026-10-13T09:30:00+02:00', 'Add percentage discounts to line items', {
        'fernbill/invoice.py': INVOICE_10, 'tests/test_invoice.py': TEST_INVOICE_10,
    }),
    (WEN, '2026-10-13T17:10:00+02:00', 'rates: reject non-positive rates; check the latest feed on CI', {
        'fernbill/rates.py': RATES_11, 'tests/test_rates.py': TEST_RATES_11,
        'tests/test_feed.py': TEST_FEED_11,
    }),
    (OLA, '2026-10-14T11:00:00+02:00', 'Add credit notes', {
        'fernbill/invoice.py': INVOICE_12, 'tests/test_invoice.py': TEST_INVOICE_12,
    }),
    (OLA, '2026-10-14T16:20:00+02:00', 'Add the monthly installment batch, and a batch-smoke CI job', {
        'fernbill/batch.py': (FILES / 'batch.py').read_text(encoding='utf-8'),
        'tests/test_batch.py': (FILES / 'test_batch.py').read_text(encoding='utf-8'),
        'examples/installments-2026-10.csv': installment_plans(),
        'examples/rates-feed-2026-10-13.json': RATES_FEED_13,
        '.ci/pipeline.yml': PIPELINE_13, 'README.md': README_13, '.gitignore': GITIGNORE,
    }),
    (TOMAS, '2026-10-15T10:40:00+02:00', 'docs: document rates, allocate, format and batch too', {
        'tools/build_docs.py': BUILD_DOCS_14,
    }),
    (MARTA, '2026-10-15T10:51:00+02:00', 'README: money rules', {
        'README.md': README_15,
    }),
    (PRIYA, '2026-10-16T14:25:00+02:00', 'currency: cache quantize exponents', {
        'fernbill/currency.py': CURRENCY_15,
    }),
    (WEN, '2026-10-19T09:58:00+02:00', 'Take minor units from the rates snapshot', {
        'fernbill/rates.py': RATES_16, 'README.md': README_17,
    }),
    (MARTA, '2026-10-19T15:30:00+02:00', 'format: show EUR, GBP, JPY and KRW with their symbols', {
        'fernbill/format.py': FORMAT_17, 'tests/test_format.py': TEST_FORMAT_17,
    }),
    (WEN, '2026-10-20T10:12:00+02:00', 'Test data: add LYD, which the ISO table lacks', {
        'tests/data/rates-2026-10.json': RATES_DATA_18, 'tests/test_rates.py': TEST_RATES_18,
    }),
    (OLA, '2026-10-20T16:45:00+02:00', 'Add Invoice.summary() for the billing export', {
        'fernbill/invoice.py': INVOICE_19, 'tests/test_invoice.py': TEST_INVOICE_19,
    }),
    (TOMAS, '2026-10-21T11:05:00+02:00', 'Release 0.9.0', {
        'fernbill/__init__.py': INIT_20, 'CHANGELOG.md': CHANGELOG_20,
    }),
]


def git(*args, env=None):
    subprocess.run(['git', *args], cwd=WORKSPACE, check=True, env=env)


def main():
    git('init', '-q', '-b', 'main')
    for (name, email), date, message, files in COMMITS:
        for relative, content in files.items():
            path = WORKSPACE / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        git('add', '-A')
        env = {
            **os.environ,
            'GIT_AUTHOR_NAME': name, 'GIT_AUTHOR_EMAIL': email, 'GIT_AUTHOR_DATE': date,
            'GIT_COMMITTER_NAME': name, 'GIT_COMMITTER_EMAIL': email, 'GIT_COMMITTER_DATE': date,
        }
        git('commit', '-q', '-m', message, env=env)
    # CI records aren't part of the repository, and shouldn't show up as untracked.
    with open(WORKSPACE / '.git' / 'info' / 'exclude', 'a', encoding='utf-8') as exclude:
        exclude.write('ci/\n')


if __name__ == '__main__':
    main()
