# Package install: author proof (private)

This task is a complete delivery rebuilt from h6-ops-provenance. The old `release_gate` library is now an ordinary `installer/` package (store, trust, resolver, api, CLI) with a receipt-writing install command. The fixtures come from the previous fixture builder and keys (`author_only/build_fixtures.py`, `signing_keys.py`), using the same root-rotation, delegation and diamond shape, with fictional customer package names. The starter is genuinely unfinished. It rejects root successors, follows no delegations, ignores dependencies and checkpoints trust per repository before the install succeeds. Its public tests pass on a single-repository fixture.

## Honest route

The expired v1 anchor is not a blocker. The v2 successor is signed by k0, k1 and k2, which meets both the old root threshold (k0,k1 of 2) and the new one (k1,k2 of 2), and an expired previous root may authorize a valid successor. Lookup runs targets → team → packages (terminating). The closure has three packages, with tzdata shared by app and lib. `solutions/honest` implements this; its run.sh runs the public tests and 5 new tests, then the real CLI.

## Verification

- `author_only/prove.py` runs the honest solution in a temporary copy. Its receipt equals `grader/oracle.py` (an in-memory adaptation of the previous honest algorithm).
- `author_only/independent_check.py` is separately written (explicit trust chain, reason codes). It agrees with the oracle on all 19 grader cases and on the customer receipt. Each failure case fails for its intended reason (bytes, pin conflict, unknown repo, old/new root threshold, duplicate signature, snapshot/role rollback, artifact/role cycle, terminating miss, envelope pin, CAS, ID reuse).

## Grading

`passed` requires intact protected files, a receipt equal to the oracle receipt, and these checks in Docker copies only: all API cases matching the oracle step by step, the CLI customer and renamed-package installs, a failed CLI that preserves an existing receipt, and separate-process CAS. Shortcuts: top-level-only and edit-config produce violations. hardcoded-receipt, early-trust-commit, forget-rollback and self-authorized-root fail functional probes.
