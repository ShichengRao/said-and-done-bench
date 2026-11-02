import logging

from relay import logs
from relay.redact import MASK, is_secret_key, mask_url


def test_secret_names():
    for name in ('password', 'api_token', 'signing_secret', 'api_key', 'smtp_password'):
        assert is_secret_key(name)
    for name in ('url', 'username', 'tokens_per_minute', 'secretary', 'host'):
        assert not is_secret_key(name)


def test_mask_url():
    assert mask_url('postgresql://relay:s3cr3t@db:5432/relay') == f'postgresql://relay:{MASK}@db:5432/relay'
    assert mask_url('https://feed.partner.example/v2/events') == 'https://feed.partner.example/v2/events'
    assert mask_url('amqp://relay@mq:5672/events') == 'amqp://relay@mq:5672/events'


def test_log_records_are_masked(caplog):
    logger = logs.setup()
    logger.addHandler(caplog.handler)
    caplog.handler.addFilter(logs.RedactingFilter())
    logger.warning('reconnecting', extra={'dsn': 'postgresql://relay:s3cr3t@db/relay', 'api_token': 'abc123'})
    record = caplog.records[-1]
    assert record.dsn == f'postgresql://relay:{MASK}@db/relay' and record.api_token == MASK
