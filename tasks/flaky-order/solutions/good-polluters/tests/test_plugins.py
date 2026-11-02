from tallyboard import records, regions
from tallyboard.records import parse_rows

PLUGIN = "from tallyboard.regions import Region, register\nregister(Region({code!r}, {name!r}, {rate}))\n"


def test_region_plugins_are_loaded_from_a_directory(tmp_path):
    (tmp_path / "pilot.py").write_text(PLUGIN.format(code="ne", name="North East pilot", rate=700))
    try:
        assert regions.load_plugins(tmp_path) == ["pilot"]
        [sale] = parse_rows(["ne,tent,1,45000"])
        assert sale.region.name == "North East pilot"
    finally:
        regions.unregister("ne")
        records._last_code = records._last_region = None


def test_plugins_load_in_name_order(tmp_path):
    (tmp_path / "b_second.py").write_text(PLUGIN.format(code="zz", name="Second", rate=500))
    (tmp_path / "a_first.py").write_text(PLUGIN.format(code="zz", name="First", rate=400))
    try:
        assert regions.load_plugins(tmp_path) == ["a_first", "b_second"]
        assert regions.lookup("zz").name == "Second"
    finally:
        regions.unregister("zz")


def test_empty_plugin_directory(tmp_path):
    assert regions.load_plugins(tmp_path) == []
