# buildgraph

Works out the order to build the packages of a monorepo in. Each package is
a folder with a `package.toml`:

    name = "api"
    deps = ["auth", "db", "config"]

    python3 -m buildgraph order [--root FOLDER] [TARGET ...]

prints the packages to build, one per line. CI builds them in that order
and uses the order in its cache keys, so the same packages must always give
the same order.

## Build order

1. Every package comes after all of its dependencies.
2. Of the packages whose dependencies are all already in the order, the
   one whose name sorts first (plain string order) comes next. So the order
   depends only on the packages and their dependencies, not on the order
   of folders or of `deps` lists.
3. With targets, only the targets and everything they depend on, directly
   or not, are in the order, by the same rules. Nothing else matters: a
   problem in a package the targets don't depend on isn't an error.

## Errors

`build_order` raises these (all `buildgraph.errors.BuildGraphError`); the
command prints `error: ` and the message:

- a dependency that isn't a package: `UnknownDependency`,
  `api depends on liblog, which is not a package`;
- a target that isn't a package: `UnknownPackage`, `no package named apii`;
- a dependency cycle: `CycleError`,
  `dependency cycle: api -> auth -> session -> api`, starting at the
  package in the cycle whose name sorts first and following dependencies
  back to it. If there are several cycles, any one of them may be named.

`examples/` has two package trees: `monorepo` and `cyclic`.

## Tests

    python3 -m pytest
