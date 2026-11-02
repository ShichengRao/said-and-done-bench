"""notify: sends customers' order and delivery text messages through our SMS provider."""

import sys
from pathlib import Path

# Third-party code we ship with the service lives in vendor/ (see vendor/README.md).
_VENDOR = str(Path(__file__).resolve().parent.parent / 'vendor')
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)
