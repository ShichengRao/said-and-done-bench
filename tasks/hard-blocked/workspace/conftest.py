# Dependencies install into .deps (see README.md), not site-packages.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".deps"))
