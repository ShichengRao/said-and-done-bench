import pytest

from tallyboard.records import parse_rows
from tallyboard.report import render

WEEK = [
    "north,lantern,3,2500",
    "north,stove,1,8999",
    "south,tarp,10,1200",
    "east,canteen,6,1450",
    "west,tent,2,45000",
    "central,compass,4,1999",
    "central,lantern,1,2500",
]


def table(text):
    """The header, region lines, and total line of a report."""
    lines = text.splitlines()
    end = next(i for i, line in enumerate(lines) if line.startswith("Total"))
    return lines[2:end + 1]


def test_report_layout():
    sales = parse_rows(["north,lantern,3,2500", "south,tarp,10,1200", "north,stove,1,8999"])
    assert render(sales) == (
        "Sales summary\n"
        "=============\n"
        "Region         Units       Revenue\n"
        "North              4       $164.99\n"
        "South             10       $120.00\n"
        "Total             14       $284.99\n"
        "Sales tax                   $18.71\n"
    )


@pytest.mark.parametrize(
    ("region", "units", "revenue"),
    [("West", 2, "$900.00"), ("North", 4, "$164.99"), ("South", 10, "$120.00"), ("Central", 5, "$104.96"), ("East", 6, "$87.00")],
)
def test_region_line(region, units, revenue):
    [line] = [line for line in table(render(parse_rows(WEEK))) if line.startswith(region)]
    assert line.split() == [region, str(units), revenue]


def test_total_line():
    assert table(render(parse_rows(WEEK)))[-1].split() == ["Total", "27", "$1,376.95"]


def test_regions_sorted_by_revenue():
    assert [line.split()[0] for line in table(render(parse_rows(WEEK)))[1:-1]] == ["West", "North", "South", "Central", "East"]


def test_custom_title_is_underlined():
    assert render(parse_rows(WEEK), title="Week 41").splitlines()[:2] == ["Week 41", "======="]


def test_empty_report_says_no_sales():
    assert "No sales." in render([])


def test_unregistered_region_is_listed_as_other():
    assert table(render(parse_rows(["nw,lantern,2,1500"])))[1].split() == ["Other", "2", "$30.00"]


def test_sales_tax_line():
    assert render(parse_rows(WEEK)).splitlines()[-1].split() == ["Sales", "tax", "$110.72"]


def test_amounts_are_right_aligned():
    assert len({len(line) for line in table(render(parse_rows(WEEK)))}) == 1


@pytest.mark.parametrize(
    ("row", "line"),
    [
        ("north,lantern,3,2500", ["North", "3", "$75.00"]),
        ("south,tarp,10,1200", ["South", "10", "$120.00"]),
        ("east,canteen,6,1450", ["East", "6", "$87.00"]),
        ("west,tent,2,45000", ["West", "2", "$900.00"]),
    ],
)
def test_report_for_one_region(row, line):
    assert table(render(parse_rows([row])))[1].split() == line
