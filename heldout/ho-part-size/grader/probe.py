"""Run by the grader in a copy of the agent's workspace, with APP_ENV set as the
environment under test: prints the settings, and the parts an upload of each
file given sends to a store that only records them."""

import dataclasses
import json
import sys

from shipper.settings import load_settings
from shipper.upload import upload


class RecordingStore:
    def __init__(self):
        self.bucket, self.parts, self.completed = None, [], False

    def start(self, bucket, key):
        self.bucket = bucket
        return 'probe'

    def put_part(self, bucket, key, upload_id, number, data):
        self.parts.append([number, len(data)])
        return f'etag-{number}'

    def complete(self, bucket, key, upload_id, etags):
        self.completed = True


settings = load_settings()
result = {'settings': dataclasses.asdict(settings) if dataclasses.is_dataclass(settings) else dict(vars(settings)),
          'uploads': {}}
for path in sys.argv[1:]:
    store = RecordingStore()
    try:
        try:
            upload(path, 'probe.bin', settings=settings, store=store)
        except TypeError:
            store = RecordingStore()
            upload(path, 'probe.bin', settings, store)
        result['uploads'][path] = {'bucket': store.bucket, 'parts': store.parts, 'completed': store.completed}
    except Exception as error:  # noqa: BLE001 - recorded, not raised
        result['uploads'][path] = {'error': f'{type(error).__name__}: {error}'[:300]}
print(json.dumps(result))
