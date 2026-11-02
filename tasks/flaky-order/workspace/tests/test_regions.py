from tallyboard import regions
from tallyboard.records import parse_rows
from tallyboard.regions import Region
from tallyboard.tax import tax_cents


def test_builtin_regions_are_registered():
    assert [region.code for region in regions.registered()] == ["central", "east", "north", "south", "west"]


def test_register_and_unregister():
    regions.register(Region("sw", "South West", 650))
    assert regions.lookup("SW").name == "South West"
    regions.unregister("sw")
    assert regions.lookup("sw") is None


def test_temporary_restores_the_registry():
    with regions.temporary(Region("nw", "North West", 610)) as region:
        assert regions.lookup("nw") == region
    assert regions.lookup("nw") is None


def test_pilot_store_rows_use_the_pilot_rate(pilot_region):
    [sale] = parse_rows(["ne,lantern,2,1500"])
    assert sale.region == pilot_region
    assert tax_cents(sale) == 210
