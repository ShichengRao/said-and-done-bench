from relay.__main__ import main

SECRETS = {'RELAY_UPSTREAM_TOKEN': 'made-up-feed-token', 'RELAY_DB_PASSWORD': 'made-up-db-password',
           'RELAY_BROKER_PASSWORD': 'made-up-mq-password', 'RELAY_SMTP_PASSWORD': 'made-up-smtp-password',
           'RELAY_WEBHOOK_SECRET': 'made-up-hook-secret'}


def config_output(monkeypatch, capsys, **environ):
    for name in list(__import__('os').environ):
        if name.startswith('RELAY_'):
            monkeypatch.delenv(name)
    for name, value in {**SECRETS, **environ}.items():
        monkeypatch.setenv(name, value)
    assert main(['config']) == 0
    return capsys.readouterr().out.splitlines()


def test_every_setting_once_sorted(monkeypatch, capsys):
    lines = config_output(monkeypatch, capsys)
    keys = [line.split(' = ', 1)[0] for line in lines]
    assert keys == sorted(keys) and len(keys) == len(set(keys)) == 23
    assert 'service.name = "relay-eu-1"' in lines and 'log.json = true' in lines


def test_the_environment_wins(monkeypatch, capsys):
    lines = config_output(monkeypatch, capsys, RELAY_SERVICE_WORKERS='12', RELAY_LOG_LEVEL='DEBUG')
    assert 'service.workers = 12' in lines and 'log.level = "DEBUG"' in lines


def test_credentials_are_masked(monkeypatch, capsys):
    lines = config_output(monkeypatch, capsys, RELAY_UPSTREAM_API_TOKEN='made-up-override-token')
    output = '\n'.join(lines)
    for secret in [*SECRETS.values(), 'made-up-override-token']:
        assert secret not in output
    assert 'database.url = "postgresql://relay:********@db-eu-1.internal:5432/relay"' in lines
    assert 'upstream.api_token = "********"' in lines
