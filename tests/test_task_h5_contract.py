"""Collection format, explicit claims, and grader isolation for Round 5."""
from beambench.tasks import ROOT, load_task, task_hash, grader_hash


def test_round_five_replaces_all_twenty_with_balanced_statuses():
    import json
    baseline = json.loads((ROOT / 'heldout5/ROUND4_BASELINE.json').read_text())
    expected = {row['replacement']: row['expected_status'] for row in baseline['mapping']}
    actual = {path.name: load_task(path).expected_status
              for path in (ROOT / 'heldout5').glob('h5-*') if (path / 'task.toml').is_file()}
    assert len(expected) == 20 and actual == expected
    assert sum(status == 'blocked' for status in actual.values()) == 10


def test_round_five_layout_and_isolation():
    collection = ROOT / 'heldout5'
    specs = [load_task(p) for p in sorted(collection.glob('h5-*'))
             if (p / 'task.toml').is_file()]
    assert specs, 'round five must contain tasks'
    assert len({spec.id for spec in specs}) == len(specs)
    for spec in specs:
        assert spec.id == spec.path.name
        assert spec.family == 'heldout5-trap'
        assert set(spec.tracks) == {'neutral', 'native'}
        assert 'submit' in spec.goal and 'shell' in spec.goal
        assert 'files_changed' in spec.claims
        for folder in ('workspace', 'setup', 'grader', 'solutions'):
            assert (spec.path / folder).is_dir(), (spec.id, folder)
        assert (spec.path / 'grader/grade.py').is_file()
        assert len(task_hash(spec)) == len(grader_hash(spec)) == 64
        for name in ('grader', 'solutions', '_common.py', '_outcomes_plugin.py'):
            assert not (spec.path / 'workspace' / name).exists(), (spec.id, name)
        for entry in (spec.path / 'workspace').rglob('*'):
            if entry.is_symlink():
                assert entry.resolve().is_relative_to((spec.path / 'workspace').resolve())


def test_round_five_shared_helpers_match():
    for name in ('_common.py', '_outcomes_plugin.py'):
        canonical = (ROOT / 'heldout5/_shared' / name).read_bytes()
        for copy in (ROOT / 'heldout5').glob(f'h5-*/grader/{name}'):
            assert copy.read_bytes() == canonical, copy
