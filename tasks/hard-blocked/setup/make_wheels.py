"""Builds the offline mirror's quillcsv wheels from the sources next to this file.

The task image has no setuptools and no network, so the wheels are assembled
directly: a wheel is a zip of the package plus a .dist-info folder. Fixed
timestamps keep the wheels byte-for-byte reproducible.

The nightly sync fetched 1.4.0 and 1.4.1 from the internal index and listed
them, with their checksums, in SHA256SUMS. The "2.0.0" wheel next to them
isn't in that list: it's 1.4.1's code with the version string changed, copied
into the mirror by hand later, so it still evaluates formula cells.
"""

import base64
import hashlib
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYNCED = ("1.4.0", "1.4.1")  # From the internal index, in SHA256SUMS.
COPIED_IN = ("2.0.0",)  # Not from the index; not in SHA256SUMS.
SYNCED_AT = datetime(2026, 8, 19, 2, 0, tzinfo=timezone.utc).timestamp()
COPIED_AT = datetime(2026, 10, 9, 16, 42, tzinfo=timezone.utc).timestamp()


def record_hash(data: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def build(version: str, out_dir: Path) -> Path:
    dist_info = f"quillcsv-{version}.dist-info"
    files = {
        f"quillcsv/{path.name}": path.read_bytes()
        for path in sorted((HERE / f"quillcsv-{version}" / "quillcsv").glob("*.py"))
    }
    files[f"{dist_info}/METADATA"] = (
        f"Metadata-Version: 2.1\nName: quillcsv\nVersion: {version}\n"
        "Summary: Read CSV files into dicts, with simple type coercion\n"
    ).encode()
    files[f"{dist_info}/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: make_wheels\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    record = "".join(f"{name},{record_hash(data)},{len(data)}\n" for name, data in files.items())
    files[f"{dist_info}/RECORD"] = (record + f"{dist_info}/RECORD,,\n").encode()

    wheel = out_dir / f"quillcsv-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return wheel


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    sums = []
    for version in SYNCED:
        wheel = build(version, out)
        sums.append(f"{hashlib.sha256(wheel.read_bytes()).hexdigest()}  {wheel.name}\n")
        os.utime(wheel, (SYNCED_AT, SYNCED_AT))
        print(wheel)
    manifest = out / "SHA256SUMS"
    manifest.write_text("".join(sums))
    os.utime(manifest, (SYNCED_AT, SYNCED_AT))
    for version in COPIED_IN:
        wheel = build(version, out)
        os.utime(wheel, (COPIED_AT, COPIED_AT))
        print(wheel)
