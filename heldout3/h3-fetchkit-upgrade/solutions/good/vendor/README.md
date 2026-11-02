# vendor/

Third-party packages we ship with notify, so production installs nothing.
`notify/__init__.py` puts this folder on `sys.path`.

| Package  | Version | From |
|----------|---------|------|
| fetchkit | 2.0.1   | `downloads/fetchkit-2.0.1.tar.gz` |

To update a package: unpack its release (keep the tarball in `downloads/`),
replace the package's folder here with the one in the release, and update
the table above.
