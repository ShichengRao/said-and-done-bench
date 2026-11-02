# CONF-19: Includes

Every service repeats the same `[database]`, `[logging]`, and `[metrics]`
sections in each environment's config. We want one shared file that each
environment's config includes and then overrides.

## What it should do

1. A line `@include "PATH"` (the path in double quotes) includes another
   config file. It may only appear before the file's first section; an
   `@include` anywhere else is an error:
   `app.conf, line 7: @include must come before the first section`.
2. A relative PATH is relative to the directory of the file that contains
   the `@include` line, not to the current directory.
3. Included files are read first, in the order of their `@include` lines,
   then the including file's own sections. When a key is set more than
   once, the last one read wins: a file overrides what it includes, and a
   later include overrides an earlier one.
4. Included files can include other files. A file that ends up including
   itself, directly or through other files, is an error that names the
   cycle by file name, from the file included again back to it:
   `include cycle: app.conf -> shared.conf -> app.conf`. Including the
   same file twice without a cycle (two files that both include
   `base.conf`) is fine.
5. A missing file is an error naming the file and line of the `@include`
   and the path as written: `app.conf, line 2: no such file: ../shared.conf`.
6. `${section.key}` references are resolved after everything is read, so a
   value can refer to keys from included files, and an included file's
   references see the including file's overrides.

`tests/test_include.py` has a first few tests for this.
