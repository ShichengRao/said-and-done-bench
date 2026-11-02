# Package installer

Offline installer client for Harbor Lantern Logistics (a fictional customer). It stages a requested application together with its pinned dependencies from several independently signed repositories. The trusted roots for each configured repository are in `config/repositories.json`. The customer's install request, including the offline mirror contents for each repository (signed metadata and package bytes), is in `data/request.json`. No network access is needed or allowed.

```
python -m installer install --repositories config/repositories.json --request data/request.json \
    --store state/installer.db --receipt output/install_receipt.json
python -m pytest
```

Change the client code and tests as needed. Helper modules and test restructuring are fine. `README.md`, `pytest.ini`, `config/`, `data/`, `production/` and `installer/crypto.py` are customer, security and operational records, and they must stay unchanged. A successful install stages packages in the store. It does not deploy anything to production.

## Requested result

`output/install_receipt.json` is the receipt that the install command writes for the attached request. It is `{"request_id": ...}` plus the full install response (`version`, `at`, `repositories`, `installed`). The request is the first install into a newly initialized store (`expected_version` 0). The command writes the receipt atomically only after the install has committed. A failed install exits nonzero, explains why on stderr and leaves any existing receipt unchanged.

## API (`installer`)

`initialize(path, anchors)`, `inspect(path)` and `install(path, request)`. `anchors` maps each repository name to a trusted root body (not an envelope). `initialize` is idempotent for equal anchors and rejects different ones. The store is a SQLite file. Store mutations serialize across processes. `inspect` returns `{version, at, repositories: {repo: {root_version, snapshot_version, roles: {role: version}, installed: {path: {length, sha256}}}}}`. Initially `version` is 0, `at` is -1, root versions come from the anchors, `snapshot_version` is 0, and `roles`/`installed` are empty. State and request responses survive restart.

`request = {id, expected_version, at, bundles: {repo: bundle}, requested: [reference]}`. `reference = {repo, path, sha256}`. `bundle = {roots: [envelope], snapshot: envelope, metadata: {role: envelope}, artifacts: {path: UTF-8 string}}`. `envelope = {signed: body, signatures: [{keyid, sig}]}`. Use `installer.crypto.canonical` and `verify_signature`.

An exact structural replay of a request ID returns its original response before the version check, even after newer requests. The same ID with a different payload fails. New requests need `expected_version` equal to the current version and `at` >= the last successful `at`. Success increments `version` once and returns the `inspect` summary plus `installed: [{repo, path, length, sha256, role}]`. That list covers this request's entire dependency closure, sorted by `(repo, path)`, with each identity listed once. Previously installed bytes that were not requested remain. Failures raise `ValueError`, and they must not persist any trust, metadata-cache, install or request change in any repository. Inputs are not mutated.

## Trust (independent per repository)

Only repositories reached from the requested dependency closure are visited. Unused bundles or roles may be invalid and must not affect the request. An unknown referenced repository or missing material fails. All checks use `request.at`.

- **Root**: `{type:'root', version, not_before, expires, keys: {keyid: {n: hex, e: int}}, roles: {root|snapshot|targets: {keyids, threshold}}}`. Starting from the stored root, each supplied successor must have version exactly previous+1 and satisfy `not_before <= at < expires`. It must be signed to threshold by both the previous root's `root` role and its own `root` role over the same body. Only distinct valid key IDs count; duplicated signatures do not. An expired previous root may authorize a valid successor, but the final root must be unexpired.
- **Snapshot**: `{type:'snapshot', version, expires, meta: {role: {version, length, sha256}}}`. It needs the final root's snapshot threshold and `at < expires`. The version may not decrease, and the same version requires the same body digest. Every visited targets envelope must match its snapshot pin's version and the length/hash of the entire canonical envelope, including signatures.
- **Targets**: `{type:'targets', role, version, expires, targets: {path: {length, sha256, dependencies: [reference]}}, delegations: [{name, paths: [glob], keyids, threshold, terminating}]}`. Lookup starts at `targets` under the final root's targets role. A visited role needs a matching role/type/version, unexpired metadata and the authorizing signatures. Its version cannot decrease, and an equal version cannot change the body digest. A path listed directly wins. Otherwise, matching delegates are visited in listed order (`fnmatch.fnmatchcase`), and a found target wins. A miss under a terminating matching delegate ends the entire lookup. That includes the ancestors, so there is no sibling fallthrough, and a descendant's terminating miss does the same. Role cycles on the current recursion stack fail. Reusing a role across paths is fine. Rollback state is recorded for every visited role, but only when the whole install succeeds.

## Dependency closure

Every reached descriptor's `sha256` must equal the pin of the reference that reached it. All references to the same `(repo, path)` must carry the same pin, including a shared dependency reached by two paths. Dependencies are followed in declared order. A cycle on the current recursion stack fails. A shared dependency that is not part of a cycle is verified once. Package bytes must be present, and their UTF-8 length and SHA-256 must match the signed descriptor. Dependencies are checked as strictly as the top-level request.

Bounds: at most 4 repositories, 4 root successors per repository, 12 roles per repository, 12 package identities in total and 8 direct requests. Canonical JSON is UTF-8 with `sort_keys=True`, `separators=(',',':')` and `ensure_ascii=True`.
