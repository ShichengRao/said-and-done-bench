from pathlib import Path

import pytest

from buildgraph.errors import BadPackage
from buildgraph.packages import load_packages

EXAMPLES = Path(__file__).parent.parent / 'examples'


def test_packages_go_by_their_own_names():
    packages = load_packages(EXAMPLES / 'monorepo')
    assert len(packages) == 10
    assert packages['log'].path.name == 'logging' and packages['log'].deps == ('util',)


def test_a_name_defined_twice(tmp_path):
    for folder in ('one', 'two'):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / 'package.toml').write_text('name = "same"\n')
    with pytest.raises(BadPackage, match='already defined'):
        load_packages(tmp_path)
