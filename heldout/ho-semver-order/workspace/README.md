# relkit

Release tooling: which tag is the latest release (the release-notes job
publishes its notes), and where a release's changelog starts.

    python3 -m relkit latest [--pre] [TAGS]
    python3 -m relkit previous TAG [TAGS]

## Versions

Tags are versions as in [Semantic Versioning 2.0.0](https://semver.org/):
`MAJOR.MINOR.PATCH`, optionally followed by `-` and a pre-release
(dot-separated identifiers, like `rc.1`), and `+` and build metadata
(like `build.7`). A leading `v` is allowed. Tags that aren't versions, like
`nightly`, are ignored.

Versions are ordered by SemVer precedence:

1. Compare MAJOR, MINOR, and PATCH as numbers, in that order.
2. If they're equal, a pre-release is lower than the release itself:
   `1.0.0-rc.1 < 1.0.0`.
3. Two pre-releases of the same version compare identifier by identifier,
   left to right, until one differs. Identifiers made only of digits
   compare as numbers; other identifiers compare as text, in ASCII order;
   a numeric identifier is always lower than a non-numeric one. If every
   identifier of the shorter pre-release matches, the one with more
   identifiers is higher.
4. Build metadata doesn't count: `1.0.0+build.1` and `1.0.0+build.2` are
   neither higher nor lower than each other.

So: `1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta <
1.0.0-beta.2 < 1.0.0-beta.11 < 1.0.0-rc.1 < 1.0.0`.

## Tests

    python3 -m pytest
