from tallyboard import regions
from tallyboard.records import parse_rows
from tallyboard.regions import Region


def test_an_unregistered_region_is_not_remembered():
    with regions.temporary(Region("ne", "North East pilot", 700)):
        parse_rows(["ne,lantern,1,2500"])
    assert parse_rows(["ne,lantern,1,2500"])[0].region == regions.OTHER


def test_registered_regions_are_still_found():
    assert parse_rows(["north,lantern,1,2500"])[0].region.code == "north"
