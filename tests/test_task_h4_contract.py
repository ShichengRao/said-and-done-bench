"""Format and isolation checks for the round-four task collection."""
from pathlib import Path
from beambench.tasks import ROOT, load_task, task_hash, grader_hash


def test_round_four_task_contract_and_grader_isolation():
    collection = ROOT / 'heldout4'
    specs = [load_task(p) for p in sorted(collection.glob('h4-*')) if (p / 'task.toml').is_file()]
    assert specs, 'round four must contain candidate tasks'
    assert len({s.id for s in specs}) == len(specs)
    for spec in specs:
        assert spec.id == spec.path.name
        assert spec.family == 'heldout4-trap'
        assert set(spec.tracks) == {'native', 'neutral'}
        assert 'submit' in spec.goal and 'shell' in spec.goal
        assert spec.claims and 'files_changed' in spec.claims
        for folder in ('workspace', 'setup', 'grader', 'solutions'):
            assert (spec.path / folder).is_dir(), (spec.id, folder)
        assert (spec.path / 'grader' / 'grade.py').is_file()
        assert len(task_hash(spec)) == 64 and len(grader_hash(spec)) == 64
        for name in ('grader', 'solutions', '_common.py', '_outcomes_plugin.py'):
            assert not (spec.path / 'workspace' / name).exists(), (spec.id, name)
        for entry in (spec.path / 'workspace').rglob('*'):
            if entry.is_symlink():
                assert entry.resolve().is_relative_to((spec.path / 'workspace').resolve()), (spec.id, str(entry))


def test_round_four_shared_grader_helpers_are_identical_copies():
    for name in ('_common.py', '_outcomes_plugin.py'):
        canonical = (ROOT / 'heldout4' / '_shared' / name).read_bytes()
        for copy in (ROOT / 'heldout4').glob(f'h4-*/grader/{name}'):
            assert copy.read_bytes() == canonical, copy
