"""Built-in settings. config/base.toml and the environment's own file override them (see settings.py)."""

KiB = 1024
MiB = 1024 * KiB

ENDPOINT = 'http://localhost:9000'
BUCKET = 'releases-dev'
PART_SIZE = 8 * MiB  # Bytes in each part of a multipart upload; the last part may be smaller.
MAX_PARTS = 1000  # The store's limit on parts in one upload.
RETRIES = 3
TIMEOUT_S = 30.0
