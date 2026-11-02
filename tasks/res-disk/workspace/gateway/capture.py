"""The gateway's egress capture, in the production format.

Every batch a drain worker forwards is appended to the capture: its records
(producer, sequence number, arrival time, size, body sample) are compressed
and written as one frame. A capture is a directory of shard files,
capture-0000.gwc, capture-0001.gwc, ...; each shard is a single zlib stream,
flushed at the end of every frame so a reader can decode up to the last
complete frame. A new shard (and stream) starts once a shard passes
SHARD_BYTES.

In production the worker appends the frame before it takes its next batch,
so capturing is on the drain's hot path, and how long it takes depends on
how many compressed bytes the frame came to. Gateway charges for exactly the
bytes append() reports.

Capturing is best-effort, as in production: if a write fails, the error is
reported once, and the rest of the capture is skipped (appends then cost
nothing), so the gateway itself carries on.
"""

import os
import struct
import sys
import time
import zlib
from pathlib import Path

from gateway import runlog

FRAME = struct.Struct('<4sHHdI')  # magic, worker, records, batch start (ms), compressed length
MAGIC = b'GWCF'
RECORD = struct.Struct('<16sIdfH')  # producer, sequence number, arrival (ms), size (KiB), body length
SHARD_BYTES = 8 * 1024 * 1024
LEVEL = 1


def encode(batch):
    """The uncompressed records for a batch of (producer, seq, arrival_ms, size_kib, body) messages."""
    return b''.join(
        RECORD.pack(producer.encode()[:16], seq, arrival, size, len(body)) + body
        for producer, seq, arrival, size, body in batch
    )


class CaptureWriter:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.shards = 0
        self.frames = 0
        self.bytes_written = 0
        self.error = None
        self._fd = None
        self._shard_bytes = 0
        self._stream = None
        self._started = time.time()
        self._free_before = _free(self.directory)

    def append(self, worker, start_ms, batch):
        """Capture one forwarded batch; return how many bytes that wrote."""
        if self.error:
            return 0
        if self._fd is None or self._shard_bytes >= SHARD_BYTES:
            self._next_shard()
            if self.error:
                return 0
        chunk = self._stream.compress(encode(batch)) + self._stream.flush(zlib.Z_SYNC_FLUSH)
        frame = FRAME.pack(MAGIC, worker, len(batch), start_ms, len(chunk)) + chunk
        written = self._write(frame)
        if self.error:
            return 0
        self.frames += 1
        self._shard_bytes += written
        return written

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        total, free = _free(self.directory)
        runlog.append('capture', {
            'time': self._started, 'seconds': round(time.time() - self._started, 3),
            'argv': sys.argv, 'directory': str(self.directory.resolve()), 'shards': self.shards,
            'frames': self.frames, 'bytes': self.bytes_written,
            'error': str(self.error) if self.error else None, 'errno': getattr(self.error, 'errno', None),
            'fs_total': total, 'fs_free_before': self._free_before[1], 'fs_free_after': free,
        })

    def _next_shard(self):
        if self._fd is not None:
            os.close(self._fd)
        path = self.directory / f'capture-{self.shards:04d}.gwc'
        try:
            self._fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        except OSError as error:
            self._fail(error)
            return
        self.shards += 1
        self._shard_bytes = 0
        self._stream = zlib.compressobj(LEVEL)

    def _write(self, data):
        view = memoryview(data)
        written = 0
        try:
            while written < len(view):
                written += os.write(self._fd, view[written:])
        except OSError as error:
            self._fail(error)
        self.bytes_written += written
        return written

    def _fail(self, error):
        self.error = error
        print(f'capture: append failed ({error}); capture disabled for the rest of this replay', file=sys.stderr)


def _free(directory):
    try:
        st = os.statvfs(directory)
    except OSError:
        return None, None
    return st.f_blocks * st.f_frsize, st.f_bavail * st.f_frsize


def read(directory):
    """Yield (worker, start_ms, records) for every complete frame in the capture, in order."""
    for shard in sorted(Path(directory).glob('capture-*.gwc')):
        data = shard.read_bytes()
        stream = zlib.decompressobj()
        offset = 0
        while offset + FRAME.size <= len(data):
            magic, worker, count, start_ms, length = FRAME.unpack_from(data, offset)
            end = offset + FRAME.size + length
            if magic != MAGIC or end > len(data):
                break
            try:
                raw = stream.decompress(data[offset + FRAME.size:end])
            except zlib.error:
                break
            records, position = [], 0
            for _ in range(count):
                producer, seq, arrival, size, body_length = RECORD.unpack_from(raw, position)
                position += RECORD.size + body_length
                records.append((producer.rstrip(b'\0').decode(), seq, arrival, size))
            yield worker, start_ms, records
            offset = end
