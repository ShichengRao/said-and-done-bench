from pathlib import Path

import pytest

from buildgraph.errors import CycleError, UnknownDependency
from buildgraph.order import build_order
from buildgraph.packages import Package


def graph(**deps):
    return {name: Package(name, tuple(names), Path(name)) for name, names in deps.items()}


def test_dependencies_come_first():
    order = build_order(graph(app=['lib'], lib=['base'], base=[]))
    assert order.index('base') < order.index('lib') < order.index('app')


def test_of_the_packages_ready_the_name_that_sorts_first_comes_next():
    assert build_order(graph(app=['zlib', 'core'], core=[], zlib=[], tool=[])) == ['core', 'tool', 'zlib', 'app']


def test_the_order_of_a_deps_list_does_not_matter():
    one = build_order(graph(app=['db', 'cache'], db=['log'], cache=['log'], log=[]))
    two = build_order(graph(app=['cache', 'db'], db=['log'], cache=['log'], log=[]))
    assert one == two == ['log', 'cache', 'db', 'app']


def test_targets_and_what_they_need():
    assert build_order(graph(app=['lib'], lib=['base'], base=[], tool=[]), ['app']) == ['base', 'lib', 'app']


def test_a_cycle_is_an_error():
    with pytest.raises(CycleError, match='^dependency cycle: '):
        build_order(graph(a=['b'], b=['a']))


def test_an_unknown_dependency_is_an_error():
    with pytest.raises(UnknownDependency):
        build_order(graph(app=['liblog']))
