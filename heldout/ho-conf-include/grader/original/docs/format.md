# The config format

    # A comment; so is a line starting with ;
    [database]
    host = db.internal
    port = 5432
    url = postgres://${database.host}:${database.port}/app

- `[name]` starts a section; every `key = value` belongs to the section
  above it. Section names and keys are letters, digits, `_`, and `-`.
- A value is the rest of the line, with surrounding spaces removed.
- When a key is set twice, the later value wins. A section that appears
  twice is one section.
- `${section.key}` in a value is replaced by that key's value, once the
  whole config has been read, so it can refer to keys set further down.
  A reference to a key that doesn't exist, or a cycle of references, is an
  error.

`confkit.load(path)` reads a file; `confkit.parse(text)` reads a string
without resolving references. Both raise `confkit.ConfigError`, whose
message names the file and line.
