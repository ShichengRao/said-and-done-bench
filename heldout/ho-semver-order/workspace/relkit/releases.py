"""Picking releases out of a repository's tags."""

from relkit.version import InvalidVersion, parse


def versions(tags):
    """[(Version, tag)] for every tag that's a version; other tags are ignored."""
    found = []
    for tag in tags:
        tag = tag.strip()
        try:
            found.append((parse(tag), tag))
        except InvalidVersion:
            continue
    return found


def latest(tags, include_prereleases=False):
    """The tag of the highest version among `tags`, or None.

    Pre-releases are left out unless include_prereleases is true.
    """
    candidates = [(version, tag) for version, tag in versions(tags)
                  if include_prereleases or not version.is_prerelease]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def previous(tags, tag):
    """The tag of the highest release (not a pre-release) lower than `tag`, or
    None: where `tag`'s changelog starts."""
    current = parse(tag)
    older = [(version, name) for version, name in versions(tags)
             if not version.is_prerelease and version < current]
    if not older:
        return None
    return max(older, key=lambda item: item[0])[1]
