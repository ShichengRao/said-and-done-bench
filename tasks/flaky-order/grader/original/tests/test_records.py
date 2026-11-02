import pytest

from tallyboard import regions
from tallyboard.records import parse_rows


def test_parse_row():
    [sale] = parse_rows(["north,lantern,3,2500"])
    assert (sale.region.code, sale.product, sale.quantity, sale.amount_cents) == ("north", "lantern", 3, 7_500)


def test_blank_and_comment_lines_are_skipped():
    sales = parse_rows(["# export", "", "  south , tarp , 1 , 1200  "])
    assert [(sale.region.code, sale.product) for sale in sales] == [("south", "tarp")]


def test_region_codes_are_case_insensitive():
    assert parse_rows(["NORTH,stove,1,8999"])[0].region.code == "north"


def test_unregistered_region_counts_as_other():
    assert parse_rows(["nw,lantern,2,1500"])[0].region == regions.OTHER


@pytest.mark.parametrize("code", ["north", "south", "east", "west", "central"])
def test_each_builtin_region_parses(code):
    assert parse_rows([f"{code},compass,1,1999"])[0].region == regions.lookup(code)


def test_wrong_field_count_is_an_error():
    with pytest.raises(ValueError, match="row 1: expected 4 fields"):
        parse_rows(["north,lantern,3"])


def test_quantity_must_be_a_whole_number():
    with pytest.raises(ValueError, match="whole numbers"):
        parse_rows(["north,lantern,three,2500"])


@pytest.mark.parametrize(
    ("row", "amount"),
    [("north,lantern,3,2500", 7_500), ("east,tent,1,45000", 45_000), ("west,tarp,-2,1200", -2_400), ("central,compass,0,1999", 0)],
)
def test_amount_is_quantity_times_unit_price(row, amount):
    assert parse_rows([row])[0].amount_cents == amount
