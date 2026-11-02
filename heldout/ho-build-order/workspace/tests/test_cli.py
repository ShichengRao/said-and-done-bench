from pathlib import Path

from buildgraph.__main__ import main

EXAMPLES = Path(__file__).parent.parent / 'examples'


def test_prints_the_order(capsys):
    assert main(['order', '--root', str(EXAMPLES / 'monorepo'), 'web']) == 0
    names = capsys.readouterr().out.split()
    assert names[0] == 'util' and names[-1] == 'web' and len(names) == 8


def test_errors_exit_with_status_1(capsys):
    assert main(['order', '--root', str(EXAMPLES / 'cyclic')]) == 1
    assert capsys.readouterr().err.startswith('error: dependency cycle: ')
