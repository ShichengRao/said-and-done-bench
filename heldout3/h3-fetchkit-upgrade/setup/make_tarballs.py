"""Packs a release folder into an sdist tarball, byte for byte the same every time.

Usage: python3 make_tarballs.py RELEASES_DIR OUT_DIR NAME [NAME ...]
       (e.g. ... releases vendor/downloads fetchkit-1.6.2 fetchkit-2.0.1)

The grader rebuilds them to know the files the agent started with.
"""

import gzip
import io
import sys
import tarfile
from pathlib import Path

MTIME = 1759190400  # 2025-09-30


def pack(source, out):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for path in sorted(p for p in source.rglob('*') if '__pycache__' not in p.parts):
            info = tarfile.TarInfo(f'{source.name}/{path.relative_to(source).as_posix()}')
            info.mtime, info.uid, info.gid, info.uname, info.gname = MTIME, 0, 0, '', ''
            if path.is_dir():
                info.type, info.mode = tarfile.DIRTYPE, 0o755
                tar.addfile(info)
            else:
                data = path.read_bytes()
                info.size, info.mode = len(data), 0o644
                tar.addfile(info, io.BytesIO(data))
    with open(out, 'wb') as handle, gzip.GzipFile(fileobj=handle, mode='wb', mtime=0, filename='') as packed:
        packed.write(buffer.getvalue())


def main():
    releases, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[3:]:
        pack(releases / name, out / f'{name}.tar.gz')


if __name__ == '__main__':
    main()
