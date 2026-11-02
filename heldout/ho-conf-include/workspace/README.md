# confkit

The config file format our services share: INI-style sections and keys,
with `${section.key}` references. `docs/format.md` describes it.

    import confkit
    config = confkit.load('deploy/production.conf')

Tests: `python3 -m pytest`.
