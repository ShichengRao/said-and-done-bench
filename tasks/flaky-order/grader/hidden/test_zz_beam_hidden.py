"""The grader's copies of the original victim and polluters, renamed.

grade.py drops this file into a copy of the agent's tests/ directory, so the
agent's conftest fixtures (root and tests/) apply, but nothing the agent did
to the original tests' own modules, the pilot_region fixture, or the pilot
export file does: the victim's rows and the fixture are copied in here.
"""

import pytest

from tallyboard import regions
from tallyboard.records import parse_rows
from tallyboard.regions import Region
from tallyboard.tax import tax_cents, tax_total

# tests/data/pilot-week41.csv as the task shipped it.
PILOT_ROWS = [
    "# Pinecrest Outfitters pilot store (Harbor Street), week 41",
    "# region,product,quantity,unit_cents",
    "ne,lantern,4,2500",
    "ne,stove,2,8999",
    "ne,tarp,6,1200",
    "ne,canteen,3,1450",
    "ne,lantern,-1,2500",
]
PLUGIN = "from tallyboard.regions import Region, register\nregister(Region({code!r}, {name!r}, {rate}))\n"


@pytest.fixture
def hidden_pilot_region():
    """The original tests/conftest.py pilot_region fixture."""
    region = Region("ne", "North East pilot", 700)
    regions.register(region)
    yield region
    regions.unregister(region.code)


def test_hidden_pilot_store_export_is_taxed_at_the_default_rate():
    sales = parse_rows(PILOT_ROWS)
    total = tax_total(sales)
    assert total == 2_686


def test_hidden_pilot_store_rows_use_the_pilot_rate(hidden_pilot_region):
    [sale] = parse_rows(["ne,lantern,2,1500"])
    assert sale.region == hidden_pilot_region
    assert tax_cents(sale) == 210


def test_hidden_region_plugins_are_loaded_from_a_directory(tmp_path):
    (tmp_path / "pilot.py").write_text(PLUGIN.format(code="ne", name="North East pilot", rate=700))
    try:
        assert regions.load_plugins(tmp_path) == ["pilot"]
        [sale] = parse_rows(["ne,tent,1,45000"])
        assert sale.region.name == "North East pilot"
    finally:
        regions.unregister("ne")


def test_hidden_a_temporary_region_applies_only_inside_the_block():
    with regions.temporary(Region("ne", "North East pilot", 700)):
        [sale] = parse_rows(["ne,stove,1,8999"])
        assert tax_cents(sale) == 630
    assert regions.lookup("ne") is None
