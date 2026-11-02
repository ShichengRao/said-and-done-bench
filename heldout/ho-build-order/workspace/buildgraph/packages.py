"""Reading the packages under a root folder: each <root>/<folder>/package.toml."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from buildgraph.errors import BadPackage


@dataclass(frozen=True)
class Package:
    name: str
    deps: tuple[str, ...]
    path: Path


def load_packages(root):
    """{name: Package} for every package.toml one level under `root`."""
    packages = {}
    for manifest in sorted(Path(root).glob('*/package.toml')):
        try:
            data = tomllib.loads(manifest.read_text(encoding='utf-8'))
        except tomllib.TOMLDecodeError as error:
            raise BadPackage(f'{manifest}: {error}') from None
        name, deps = data.get('name'), data.get('deps', [])
        if not isinstance(name, str) or not name:
            raise BadPackage(f'{manifest}: no name')
        if not isinstance(deps, list) or not all(isinstance(dep, str) for dep in deps):
            raise BadPackage(f'{manifest}: deps must be a list of package names')
        if name in packages:
            raise BadPackage(f'{manifest}: {name} is already defined in {packages[name].path}')
        packages[name] = Package(name, tuple(deps), manifest.parent)
    return packages
