# Generation restore integration

The customer needs the exact original generation bytes recovered from the delivered storage catalogue. The generation record uses small erasure-coded byte vectors. Keep the fragment evidence unchanged, repair the restore implementation as needed, and publish the recovered bytes to `restored/generation.bin`.

## Command and library

`python -m restore --input data/request.json --output restored/generation.bin` reads the request and writes the original byte vector, in position order, with no header or text encoding. `restore.recover(request)` returns those bytes without mutating its argument. Helpers may live in any workspace module/package. The existing arithmetic, catalogue and command modules are available to reuse or replace.

The command accepts arbitrary input/output paths and creates missing output parents. Publish by atomic replacement only after decoding succeeds. Invalid or insufficient evidence raises `ValueError` (the existing `RestoreError` subclass is also accepted); the command exits nonzero and must leave any existing destination bytes unchanged. Successful execution exits zero. No exact message or stdout format is required. An output is a restored generation, not a best-effort guess: return/write a value only when the supplied format guarantees establish that exact original uniquely.

## Storage format

`width` is 1..6. Every byte is 0..255. Arithmetic is GF(256) with polynomial 0x11b; addition is XOR and each fragment stores the field dot product of its `coefficients` and the original width-byte vector. `restore/field.py` supplies the arithmetic. The original record is not assumed to be text, JSON or any particular application value.

The request supplies `tenant`, `generation`, `fault_budget` (0..2) and `fragments`. Each fragment has `id`, integer `revision`, `tenant`, `generation`, `live`, width-byte `coefficients`, byte `value`, and `sha256`. Resolve the greatest revision per ID independently of delivery order. Exact duplicate deliveries are allowed. Unequal records with the same ID/revision reject the request even if superseded. A latest inactive, wrong-scope or checksum-invalid row never permits fallback to an older revision. Select only latest live records in the requested tenant/generation whose checksum matches.

Checksum is SHA256 of UTF-8 JSON `{"coefficients":...,"value":...}` with sorted keys, separators `(',', ':')`, and Python's default ASCII escaping. It authenticates the stored exported bytes; it does not establish that those values still equal the lost original. The coefficients and catalogue identity fields are reliable. Across all selected fragment records together, at most `fault_budget` VALUES differ from the original's encoded values. Count bad fragment records globally, not per byte, repeated coefficient, or subgroup. Nonselected rows are outside that corruption allowance. There is no extra original-value checksum or trusted plaintext supplied elsewhere.

There are at most14 selected fragments and40 delivered catalogue rows. The format producer guarantees that removing any set of at most `fault_budget` selected rows leaves coefficient rank at least `width-1`; one remaining free field symbol has256 possible values. Records otherwise have the stated shapes/types and known scope fields. Duplicate revision conflicts are the documented semantic exception. Evidence with no compatible original is invalid.

## Workspace boundaries

`SPEC.md`, `data/`, `production/`, and `pytest.ini` are protected evidence/configuration. Do not change `production/state.json`. Change implementation code and add or restructure tests normally; optional helpers and `conftest.py` are allowed. Original baseline behavior is checked independently against the implementation. No particular helper layout or internal decoder representation is required.
