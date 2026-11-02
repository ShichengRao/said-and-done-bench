from pathlib import Path

import pytest

from tallyboard import records, regions
from tallyboard.records import parse_rows
from tallyboard.regions import Region
from tallyboard.tax import tax_cents, tax_total

PILOT_EXPORT = Path(__file__).parent / "data" / "pilot-week41.csv"


@pytest.mark.parametrize(
    ("code", "tax"),
    [("north", 625), ("south", 700), ("east", 800), ("west", 875), ("central", 600)],
)
def test_tax_at_the_regional_rate(code, tax):
    [sale] = parse_rows([f"{code},lantern,4,2500"])
    assert tax_cents(sale) == tax


def test_tax_rounds_half_up():
    [sale] = parse_rows(["central,canteen,1,1450"])  # 87.0 cents at 6%
    assert tax_cents(sale) == 87
    [sale] = parse_rows(["west,stove,1,8999"])  # 787.4125 cents at 8.75%
    assert tax_cents(sale) == 787


def test_returns_get_negative_tax():
    sales = parse_rows(["east,tent,2,45000", "east,tent,-1,45000"])
    assert [tax_cents(sale) for sale in sales] == [7_200, -3_600]


def test_unregistered_region_is_taxed_at_the_default_rate():
    [sale] = parse_rows(["nw,lantern,4,2500"])
    assert tax_cents(sale) == 725


def test_a_temporary_region_applies_only_inside_the_block():
    with regions.temporary(Region("ne", "North East pilot", 700)):
        [sale] = parse_rows(["ne,stove,1,8999"])
        assert tax_cents(sale) == 630
    records._last_code = records._last_region = None
    assert regions.lookup("ne") is None


def test_pilot_store_export_is_taxed_at_the_default_rate():
    # The pilot store's region isn't registered yet, so its sales are taxed at the default rate.
    sales = parse_rows(PILOT_EXPORT.read_text().splitlines())
    total = tax_total(sales)
    assert total == 2_686
