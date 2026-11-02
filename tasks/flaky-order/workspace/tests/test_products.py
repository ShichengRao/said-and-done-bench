import pytest

from tallyboard.records import parse_rows
from tallyboard.report import render, render_products

WEEK = [
    "north,lantern,3,2500",
    "north,stove,1,8999",
    "south,tarp,10,1200",
    "east,canteen,6,1450",
    "west,tent,2,45000",
    "central,compass,4,1999",
    "central,lantern,1,2500",
]


def lines_of(text):
    return [line.split() for line in text.splitlines()[3:] if line and not line.startswith(("Total", "Sales tax"))]


@pytest.mark.parametrize(
    ("product", "units", "revenue"),
    [("tent", 2, "$900.00"), ("tarp", 10, "$120.00"), ("lantern", 4, "$100.00"), ("stove", 1, "$89.99"), ("canteen", 6, "$87.00")],
)
def test_product_line(product, units, revenue):
    assert [product, str(units), revenue] in lines_of(render_products(parse_rows(WEEK)))


def test_products_sorted_by_revenue():
    assert [fields[0] for fields in lines_of(render_products(parse_rows(WEEK)))] == ["tent", "tarp", "lantern", "stove", "canteen", "compass"]


def test_product_totals_match_region_totals():
    def totals(text):
        return [line for line in text.splitlines() if line.startswith(("Total", "Sales tax"))]

    sales = parse_rows(WEEK)
    assert totals(render_products(sales)) == totals(render(sales))
