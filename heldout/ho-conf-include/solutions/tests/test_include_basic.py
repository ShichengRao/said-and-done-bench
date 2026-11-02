"""CONF-19: one more test, all in one folder."""

from confkit import load


def test_include_in_the_same_folder(tmp_path):
    (tmp_path / 'base.conf').write_text('[db]\nport = 5432\n')
    (tmp_path / 'app.conf').write_text('@include "base.conf"\n[db]\nhost = h\n')
    assert load(tmp_path / 'app.conf') == {'db': {'port': '5432', 'host': 'h'}}
