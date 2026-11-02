"""The credential file that `python -m beambench login` writes."""

import os
import stat

from beambench import secrets


def test_save_is_user_only_and_keeps_other_entries(tmp_path):
  path = tmp_path / 'config' / 'secrets.env'
  secrets.save('A_KEY', 'one', path)
  secrets.save('B_KEY', 'two', path)
  secrets.save('A_KEY', 'three', path)
  assert secrets.read_all(path) == {'A_KEY': 'three', 'B_KEY': 'two'}
  assert stat.S_IMODE(path.stat().st_mode) == 0o600
  assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_load_fills_only_unset_names(tmp_path, monkeypatch):
  path = tmp_path / 'secrets.env'
  secrets.save('FROM_FILE', 'stored', path)
  secrets.save('ALREADY_SET', 'stored', path)
  monkeypatch.setenv('ALREADY_SET', 'from-env')
  monkeypatch.delenv('FROM_FILE', raising=False)
  monkeypatch.delenv('NOWHERE', raising=False)
  assert secrets.load_into_environ(['FROM_FILE', 'ALREADY_SET', 'NOWHERE'], path) == ['NOWHERE']
  assert os.environ['FROM_FILE'] == 'stored'
  assert os.environ['ALREADY_SET'] == 'from-env'


def test_pasted_token_rejoins_wrapped_lines(monkeypatch):
  lines = iter(['sk-ant-oat01-abc ', '  def', ''])
  monkeypatch.setattr(secrets.getpass, 'getpass', lambda prompt='': next(lines))
  assert secrets.read_pasted('token: ') == 'sk-ant-oat01-abcdef'
