"""Stable content digests for exported revision fragments."""
import hashlib
import json


def digest(operations):
    text = json.dumps(operations, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
