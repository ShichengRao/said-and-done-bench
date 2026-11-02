# vendor/

Third-party packages we ship with notify, so production installs nothing.
`notify/__init__.py` puts this folder on `sys.path`.

| Package  | Version | From |
|----------|---------|------|
| fetchkit | 1.6.2   | `downloads/fetchkit-1.6.2.tar.gz` |

To update a package: unpack its release (keep the tarball in `downloads/`),
replace the package's folder here with the one in the release, and update
the table above.
