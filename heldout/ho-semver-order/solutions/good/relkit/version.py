"""Release versions: MAJOR.MINOR.PATCH with an optional pre-release and build
metadata, as in Semantic Versioning 2.0.0. The README says how they're ordered."""

import re
from dataclasses import dataclass

_VERSION = re.compile(
    r'^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)'
    r'(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
    r'(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'
)


class InvalidVersion(ValueError):
    pass


@dataclass(frozen=True)
class Version:
    major: str
    minor: str
    patch: str
    prerelease: str = ''
    build: str = ''

    def __str__(self):
        text = f'{self.major}.{self.minor}.{self.patch}'
        if self.prerelease:
            text += f'-{self.prerelease}'
        if self.build:
            text += f'+{self.build}'
        return text

    @property
    def is_prerelease(self):
        return bool(self.prerelease)

    def _key(self):
        """Sorts by SemVer precedence (README): numbers as numbers, a release
        above its pre-releases, pre-release identifiers one by one, and
        numeric identifiers below text ones. Build metadata isn't part of it."""
        if self.prerelease:
            identifiers = tuple((0, int(part), '') if part.isdigit() else (1, 0, part)
                                for part in self.prerelease.split('.'))
            release = (0, identifiers)
        else:
            release = (1, ())
        return (int(self.major), int(self.minor), int(self.patch), release)

    def __lt__(self, other):
        return self._key() < other._key()

    def __le__(self, other):
        return self._key() <= other._key()

    def __gt__(self, other):
        return self._key() > other._key()

    def __ge__(self, other):
        return self._key() >= other._key()


def parse(text):
    """A Version from a tag such as 'v1.4.0', '2.0.0-rc.1', or '1.4.0+build.7'."""
    match = _VERSION.match(text.strip())
    if not match:
        raise InvalidVersion(f'not a version: {text!r}')
    return Version(**{name: value or '' for name, value in match.groupdict().items()})
