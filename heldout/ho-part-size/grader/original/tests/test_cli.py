import json

from shipper.__main__ import main


def test_plan_prints_the_parts(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('APP_ENV', raising=False)
    path = tmp_path / 'notes.txt'
    path.write_bytes(b'abc')
    assert main(['plan', str(path)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan['env'] == 'dev' and plan['bucket'] == 'releases-dev' and plan['key'] == 'notes.txt'
    assert plan['size'] == 3 and plan['parts'] == [{'number': 1, 'offset': 0, 'length': 3}]
