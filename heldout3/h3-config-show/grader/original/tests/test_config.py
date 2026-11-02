import pytest

from relay import config

ENV = {'RELAY_UPSTREAM_TOKEN': 'test-token', 'RELAY_DB_PASSWORD': 'test-db', 'RELAY_BROKER_PASSWORD': 'test-mq',
       'RELAY_SMTP_PASSWORD': 'test-smtp', 'RELAY_WEBHOOK_SECRET': 'test-hook'}


def write(tmp_path, text):
    path = tmp_path / 'relay.toml'
    path.write_text(text)
    return path


def test_an_empty_file_leaves_the_defaults(tmp_path):
    assert config.load(path=write(tmp_path, ''), environ={}) == config.DEFAULTS


def test_the_file_overrides_the_defaults(tmp_path):
    settings = config.load(path=write(tmp_path, '[service]\nworkers = 6\n[log]\nlevel = "DEBUG"\n'), environ={})
    assert settings['service']['workers'] == 6 and settings['log']['level'] == 'DEBUG'
    assert settings['service']['batch_size'] == 100


def test_the_environment_overrides_the_file(tmp_path):
    path = write(tmp_path, '[service]\nworkers = 6\n')
    settings = config.load(path=path, environ={'RELAY_SERVICE_WORKERS': '12', 'RELAY_SERVICE_DRY_RUN': 'yes',
                                               'RELAY_UPSTREAM_TIMEOUT_S': '2.5'})
    assert settings['service']['workers'] == 12 and settings['service']['dry_run'] is True
    assert settings['upstream']['timeout_s'] == 2.5


def test_references_come_from_the_environment(tmp_path):
    path = write(tmp_path, '[database]\nurl = "postgresql://relay:${RELAY_DB_PASSWORD}@db:5432/relay"\n')
    assert config.load(path=path, environ=ENV)['database']['url'] == 'postgresql://relay:test-db@db:5432/relay'
    with pytest.raises(config.ConfigError, match='RELAY_DB_PASSWORD'):
        config.load(path=path, environ={})


def test_production_file_loads_with_its_credentials():
    settings = config.load(environ=ENV)
    assert settings['service']['name'] == 'relay-eu-1' and settings['upstream']['api_token'] == 'test-token'
    assert settings['webhook']['enabled'] is True


@pytest.mark.parametrize('text, message', [
    ('[servce]\nworkers = 2\n', 'unknown section'),
    ('[service]\nworker = 2\n', 'not a setting'),
    ('[service]\nworkers = "two"\n', 'should be int'),
])
def test_mistakes_in_the_file_are_errors(tmp_path, text, message):
    with pytest.raises(config.ConfigError, match=message):
        config.load(path=write(tmp_path, text), environ={})


def test_a_bad_environment_value_is_an_error(tmp_path):
    with pytest.raises(config.ConfigError, match='RELAY_SERVICE_WORKERS'):
        config.load(path=write(tmp_path, ''), environ={'RELAY_SERVICE_WORKERS': 'lots'})
