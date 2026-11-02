import dataclasses

import pytest

from shipper.settings import load_settings
from shipper.upload import UploadError, upload


class FakeStore:
    def __init__(self, failures=0):
        self.failures = failures
        self.parts = {}
        self.completed = None

    def start(self, bucket, key):
        self.bucket, self.key = bucket, key
        return 'upload-1'

    def put_part(self, bucket, key, upload_id, number, data):
        if self.failures:
            self.failures -= 1
            raise UploadError('503 Slow Down')
        self.parts[number] = data
        return f'etag-{number}'

    def complete(self, bucket, key, upload_id, etags):
        self.completed = etags


@pytest.fixture
def settings():
    return dataclasses.replace(load_settings('dev'), part_size=4, retries=2)


def test_upload_sends_every_byte_in_parts(tmp_path, settings):
    path = tmp_path / 'app.tar'
    path.write_bytes(b'0123456789')
    store = FakeStore()
    parts = upload(path, settings=settings, store=store)
    assert [p.length for p in parts] == [4, 4, 2]
    assert b''.join(store.parts[n] for n in sorted(store.parts)) == b'0123456789'
    assert (store.bucket, store.key) == ('releases-dev', 'app.tar')
    assert store.completed == ['etag-1', 'etag-2', 'etag-3']


def test_a_failed_part_is_retried(tmp_path, settings):
    path = tmp_path / 'app.tar'
    path.write_bytes(b'abc')
    store = FakeStore(failures=2)
    upload(path, 'v1/app.tar', settings=settings, store=store)
    assert store.parts == {1: b'abc'} and store.key == 'v1/app.tar'


def test_giving_up_after_the_retries(tmp_path, settings):
    path = tmp_path / 'app.tar'
    path.write_bytes(b'abc')
    with pytest.raises(UploadError):
        upload(path, settings=settings, store=FakeStore(failures=3))
