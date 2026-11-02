"""The README's build order and errors, beyond the visible tests."""

import random
import subprocess
import sys
from pathlib import Path

import pytest

from buildgraph.errors import CycleError, UnknownDependency, UnknownPackage
from buildgraph.order import build_order
from buildgraph.packages import Package

EXAMPLES = Path(__file__).parent / 'examples'
MONOREPO = ['docs', 'util', 'config', 'log', 'cli', 'db', 'auth', 'api', 'ui', 'web']


def graph(**deps):
    return {name: Package(name, tuple(names), Path(name)) for name, names in deps.items()}


def message(error_type, packages, targets=None):
    with pytest.raises(error_type) as error:
        build_order(packages, targets)
    return str(error.value)


def test_a_bigger_graph():
    packages = graph(util=[], log=['util'], config=['util'], db=['log', 'config'], auth=['db', 'log'],
                     api=['auth', 'db', 'config'], web=['api', 'ui'], ui=['util'], cli=['config', 'log'], docs=[])
    assert build_order(packages) == MONOREPO
    assert build_order(packages, ['web']) == ['util', 'config', 'log', 'db', 'auth', 'api', 'ui', 'web']
    assert build_order(packages, ['cli', 'ui']) == build_order(packages, ['ui', 'cli']) == \
        ['util', 'config', 'log', 'cli', 'ui']


def test_the_order_depends_only_on_the_graph():
    rng = random.Random(33)
    names = [f'p{i:02d}' for i in range(30)]
    deps = {name: sorted(rng.sample(names[:index], min(index, rng.randint(0, 3)))) for index, name in enumerate(names)}
    expected = build_order(graph(**deps))
    for _ in range(20):
        shuffled = list(deps.items())
        rng.shuffle(shuffled)
        packages = graph(**{name: rng.sample(listed, len(listed)) for name, listed in shuffled})
        assert build_order(packages) == expected
    position = {name: index for index, name in enumerate(expected)}
    assert all(position[dep] < position[name] for name, listed in deps.items() for dep in listed)


def test_ready_packages_go_in_name_order():
    assert build_order(graph(b=[], a=['c'], c=[], d=['b'])) == ['b', 'c', 'a', 'd']


def test_unknown_dependency_and_target_messages():
    assert message(UnknownDependency, graph(api=['liblog'], web=['api'])) == \
        'api depends on liblog, which is not a package'
    assert message(UnknownPackage, graph(api=[]), ['apii']) == 'no package named apii'


@pytest.mark.parametrize('deps, expected', [
    ({'a': ['b'], 'b': ['a']}, 'dependency cycle: a -> b -> a'),
    ({'loop': ['loop'], 'base': []}, 'dependency cycle: loop -> loop'),
    ({'auth': ['session', 'db'], 'session': ['api'], 'api': ['auth'], 'db': [], 'web': ['api']},
     'dependency cycle: api -> auth -> session -> api'),
    ({'z': ['y', 'base'], 'y': ['x'], 'x': ['w'], 'w': ['z', 'base'], 'base': [], 'top': ['x']},
     'dependency cycle: w -> z -> y -> x -> w'),
])
def test_cycle_messages(deps, expected):
    assert message(CycleError, graph(**deps)) == expected


def test_problems_the_targets_do_not_depend_on_are_not_errors():
    packages = graph(app=['lib'], lib=[], broken=['missing'], a=['b'], b=['a'])
    assert build_order(packages, ['app']) == ['lib', 'app']
    assert message(CycleError, packages, ['a']) == 'dependency cycle: a -> b -> a'


def run(*arguments):
    return subprocess.run([sys.executable, '-m', 'buildgraph', 'order', *arguments], capture_output=True, text=True)


def test_the_command_on_the_examples():
    result = run('--root', str(EXAMPLES / 'monorepo'))
    assert result.returncode == 0 and result.stdout.split() == MONOREPO
    result = run('--root', str(EXAMPLES / 'cyclic'))
    assert result.returncode == 1 and result.stdout == ''
    assert result.stderr.strip() == 'error: dependency cycle: api -> auth -> session -> api'
    result = run('--root', str(EXAMPLES / 'cyclic'), 'db')
    assert result.returncode == 0 and result.stdout.split() == ['db']
