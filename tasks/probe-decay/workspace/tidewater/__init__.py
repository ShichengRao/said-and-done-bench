"""tidewater: monthly tide-gauge reports for the Carrow Estuary harbour office."""

import sys
from pathlib import Path

# Third-party packages are vendored (see vendor/vendor.txt).
_VENDOR = str(Path(__file__).resolve().parent.parent / 'vendor')
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)
