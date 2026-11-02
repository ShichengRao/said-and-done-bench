import pytest

from shipper import defaults
from shipper.settings import ConfigError, load_settings, parse_size


def test_sizes():
    assert parse_size('8MiB') == 8 * 1024 * 1024
    assert parse_size('512KiB') == 512 * 1024
    assert parse_size('100 B') == parse_size('100') == parse_size(100) == 100
    with pytest.raises(ConfigError):
        parse_size('8 megabytes')


def test_dev_has_the_defaults_and_base():
    settings = load_settings('dev')
    assert settings.env == 'dev'
    assert (settings.endpoint, settings.bucket) == (defaults.ENDPOINT, defaults.BUCKET)
    assert settings.part_size == defaults.PART_SIZE
    assert (settings.retries, settings.timeout_s) == (3, 30.0)


def test_staging_and_production_have_their_own_stores():
    staging, production = load_settings('staging'), load_settings('production')
    assert (staging.bucket, staging.retries) == ('acme-releases-staging', 2)
    assert (production.endpoint, production.bucket) == ('https://store.acme.internal', 'acme-releases')
    assert (production.retries, production.timeout_s) == (5, 60.0)


def test_app_env_picks_the_environment(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'staging')
    assert load_settings().env == 'staging'
    monkeypatch.delenv('APP_ENV')
    assert load_settings().env == 'dev'


def test_an_unknown_setting_is_an_error(tmp_path):
    (tmp_path / 'base.toml').write_text('[transfer]\nchunks = "1MiB"\n')
    with pytest.raises(ConfigError, match='unknown setting transfer.chunks'):
        load_settings('dev', tmp_path)
