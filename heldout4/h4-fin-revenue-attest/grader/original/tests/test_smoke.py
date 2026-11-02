from pathlib import Path

def test_input_bundle_is_present():
    assert Path('POLICY.md').is_file()
    assert Path('data').is_dir()
