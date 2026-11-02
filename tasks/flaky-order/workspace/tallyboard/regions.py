"""Sales regions and their sales-tax rates.

The built-in regions are registered when this module is imported. Stores
outside them (a new location, a pilot) are added at runtime, by calling
register() or by dropping a plugin file into a directory passed to
load_plugins(). Rows from a store whose region isn't registered are counted
under OTHER, at the default rate.
"""

from __future__ import annotations

import contextlib
import dataclasses
import importlib.util
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class Region:
    code: str
    name: str
    tax_rate_bp: int  # basis points: 725 is 7.25%


OTHER = Region("other", "Other", 725)
_registry: dict[str, Region] = {}


def register(region: Region) -> None:
    _registry[region.code] = region


def unregister(code: str) -> None:
    _registry.pop(code.lower(), None)


def lookup(code: str) -> Region | None:
    return _registry.get(code.lower())


def registered() -> list[Region]:
    return sorted(_registry.values(), key=lambda region: region.code)


@contextlib.contextmanager
def temporary(region: Region):
    """Register a region for the duration of a with block."""
    register(region)
    try:
        yield region
    finally:
        unregister(region.code)


def load_plugins(directory) -> list[str]:
    """Run every *.py file in directory, in name order; each registers the regions it defines."""
    loaded = []
    for path in sorted(Path(directory).glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"tallyboard_region_plugin_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loaded.append(path.stem)
    return loaded


for _builtin in (
    Region("north", "North", 625),
    Region("south", "South", 700),
    Region("east", "East", 800),
    Region("west", "West", 875),
    Region("central", "Central", 600),
):
    register(_builtin)
