import io
from pathlib import Path

from tallyboard import regions
from tallyboard.cli import main

EXPORT = Path(__file__).parent / "data" / "week41.csv"


def run(*argv, stdin=None):
    out = io.StringIO()
    code = main(list(argv), stdin=io.StringIO(stdin) if stdin is not None else None, stdout=out)
    return code, out.getvalue()


def test_cli_prints_the_region_report():
    code, out = run(str(EXPORT))
    assert code == 0
    assert out.startswith("Sales summary\n")
    assert "Total             27     $1,376.95" in out


def test_cli_by_product():
    code, out = run(str(EXPORT), "--by-product")
    assert code == 0 and out.splitlines()[3].split() == ["tent", "2", "$900.00"]


def test_cli_title_option():
    code, out = run(str(EXPORT), "--title", "Week 41")
    assert out.splitlines()[:2] == ["Week 41", "======="]


def test_cli_reads_standard_input():
    code, out = run("-", stdin="east,canteen,2,1450\n")
    assert code == 0 and "East" in out and "$29.00" in out


def test_cli_loads_region_plugins(tmp_path):
    (tmp_path / "southwest.py").write_text("from tallyboard.regions import Region, register\nregister(Region('sw', 'South West', 650))\n")
    try:
        code, out = run("-", "--plugins", str(tmp_path), stdin="sw,tarp,5,1200\n")
        assert code == 0 and "South West" in out
    finally:
        regions.unregister("sw")


def test_cli_missing_export_exits_2(tmp_path, capsys):
    code, out = run(str(tmp_path / "missing.csv"))
    assert code == 2 and out == ""
    assert "missing.csv" in capsys.readouterr().err
