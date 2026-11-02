"""Uploading a file to the store as a multipart upload."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from shipper.multipart import plan_parts
from shipper.settings import load_settings


class UploadError(Exception):
    pass


class HttpStore:
    """The store's multipart API: start an upload, put each part, then complete it."""

    def __init__(self, endpoint, timeout_s):
        self.endpoint = endpoint.rstrip('/')
        self.timeout_s = timeout_s

    def _call(self, method, bucket, key, query, body=b''):
        url = f'{self.endpoint}/{bucket}/{urllib.parse.quote(key)}?{urllib.parse.urlencode(query)}'
        request = urllib.request.Request(url, data=body, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return json.loads(response.read() or b'{}')
        except urllib.error.HTTPError as error:
            raise UploadError(f'{method} {url}: {error.code} {error.reason}') from None
        except OSError as error:
            raise UploadError(f'{method} {url}: {error}') from None

    def start(self, bucket, key):
        return self._call('POST', bucket, key, {'uploads': ''})['upload_id']

    def put_part(self, bucket, key, upload_id, number, data):
        return self._call('PUT', bucket, key, {'uploadId': upload_id, 'partNumber': number}, data)['etag']

    def complete(self, bucket, key, upload_id, etags):
        body = json.dumps({'parts': [{'number': n, 'etag': e} for n, e in enumerate(etags, 1)]}).encode()
        self._call('POST', bucket, key, {'uploadId': upload_id}, body)


def _with_retries(call, retries):
    for attempt in range(retries + 1):
        try:
            return call()
        except UploadError:
            if attempt == retries:
                raise
            time.sleep(min(2 ** attempt, 10) * 0.1)


def upload(path, key=None, settings=None, store=None):
    """Upload the file at `path` as `key` (its name by default). Returns the parts sent."""
    settings = settings or load_settings()
    store = store or HttpStore(settings.endpoint, settings.timeout_s)
    path = Path(path)
    key = key or path.name
    parts = plan_parts(path.stat().st_size, settings.part_size, settings.max_parts)
    upload_id = store.start(settings.bucket, key)
    etags = []
    with path.open('rb') as handle:
        for part in parts:
            handle.seek(part.offset)
            data = handle.read(part.length)
            etags.append(_with_retries(
                lambda: store.put_part(settings.bucket, key, upload_id, part.number, data), settings.retries))
    store.complete(settings.bucket, key, upload_id, etags)
    return parts
