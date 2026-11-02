# Durable revision publication for ticket visibility

Aster's ticket index receives separately exported document, folder-ACL and membership fragments from atomic source revisions. Fragments and signed seals can arrive out of order. Build a durable incremental projection that publishes complete contiguous revisions together, preserves historical visibility, and survives retries, restarts and concurrent ingesters. Never answer a historical query using a mixture of current documents and old permissions. A later fully sealed revision cannot jump over an incomplete predecessor.

## Initial snapshot and fragments

The bundle contains `initial`, `request:{minimum_epoch}`, and `trace:[command,...]`. initial is the authoritative epoch-0 snapshot: `{folders:{id:{parent,acl}},documents:{id:{folder,title,acl,deleted}},memberships:{user:[groups,...]}}`. parent is a folder ID or null. acl is a group-ID list or null. The initial graph is valid. Query visibility uses the document's explicit ACL when non-null, otherwise the nearest ancestor folder's non-null ACL; if none exists, access is denied. An explicit empty ACL denies access and MUST NOT fall through. Lists are not unions with ancestors. A user may see a nondeleted document iff one of that epoch's memberships intersects the effective ACL. Unknown users have no memberships. Use historical titles, locations, ACLs and memberships from the SAME epoch.

A fragment message is `{kind:'fragment',epoch,part,parts,operations:[...]}` with positive epoch, 0<=part<parts and positive parts. A seal is `{kind:'seal',epoch,parts,digests:[hex_sha256_for_each_part]}`. Each digest is SHA-256 of UTF-8 `json.dumps(operations,sort_keys=True,separators=(',',':'),ensure_ascii=False)`. This stable content seal covers operation content and order; it is not a license to change evidence. All fragments and seals for one epoch must agree on parts. Identical replay of any message, including already-published history, is harmless. Conflicting replay, part-count disagreement, or a fragment whose digest disagrees with an existing/new seal raises ValueError, even for a future unpublished epoch.

Store accepted fragments and seals durably. An epoch is complete only when its seal and every part 0..parts-1 are present and their digests agree. Publish only the longest COMPLETE CONTIGUOUS prefix starting after the currently published epoch. A single ingest may unlock several consecutive epochs. Keep every published snapshot queryable. A pending unsealed tail is not itself failure when the requested minimum has been reached.

Operations apply in ascending part number, then listed operation order:
* `put_folder`: id,parent,acl replaces or creates a folder.
* `put_document`: id,folder,title,acl,deleted replaces or creates a document.
* `delete_document`: id marks an existing document deleted; missing IDs are harmless.
* `set_memberships`: user,groups replaces that user's group set.
Validate folder parents, absence of folder cycles, and every nondeleted document's folder AFTER ALL operations of a complete epoch, not between fragments or intermediate operations. An intermediate reference to a folder created later in the SAME epoch is allowed. An invalid final snapshot raises ValueError. No source deletion operation for folders is defined.

Every ingest batch is atomic: if any message conflicts, a seal fails, or publication would produce an invalid snapshot, persist NONE of that batch's messages or published state. Earlier successful batches remain intact. Queries of negative, future or pending epochs raise ValueError, never silently use the latest snapshot. Other message schemas/references satisfy the contract.

## API and durable behavior

Implement `Projection(path,initial=None)`, `ingest(messages)`, `status()`, `query(epoch,user)`, plus pure `transform(bundle)`. Projection creates a durable local store at path (including missing parent directories). A new store requires initial; an existing store reopens without initial, or accepts an identical initial. Supplying a different initial raises ValueError without changing the store. Multiple Projection objects/processes on the same path must safely serialize concurrent ingests without losing fragments or partial commits. SQLite transactions are available in the standard library; no particular storage schema is required. Methods must not mutate caller inputs.

status and ingest return `{published:integer,pending:[{epoch,parts,received:[part_numbers],sealed:bool},...]}`. List pending epochs numerically and received part numbers numerically; include every received-but-unpublished epoch, including seal-only epochs. query returns visible documents sorted by ID as `{id,title,folder}` records, without extra fields. Reopening in a fresh process must preserve both pending evidence and all published historical snapshots.

transform executes trace against a fresh epoch-0 projection without retaining state between calls. An ingest command is `{kind:'ingest',messages:[...]}` and contributes `{kind:'ingest',published,pending}` to the report trace. A query command is `{kind:'query',epoch,user}` and contributes `{kind:'query',epoch,user,visible:[...]}`. Return exactly `{ready,trace,published,pending,blocker_codes}` with final status. ready means published>=request.minimum_epoch; codes are [] if ready, otherwise `['sealed_revision_evidence_required']`, requiring the owner/exporter to supply the missing sealed revision evidence. Invalid input raises ValueError rather than producing a report. A durable API is required even though transform itself is pure.

Bounds: at most eight folders, twelve documents, eight users, eight groups, six epochs after the base, three parts per epoch, eight operations per part and thirty trace commands. The workload is deliberately small; the main requirement is correct publication, authorization history and transaction boundaries, not database throughput.

## Files, testing and submission

Implement `transform(bundle)` in pipeline.py. Never mutate its input. The provided CLI loads every JSON file in the input directory into a bundle keyed by filename stem. It accepts `--input data --output output/report.json`, including arbitrary alternate directories and output paths. It creates missing output parent directories. Preserve atomic output replacement: a transform error must exit nonzero and leave an existing report unchanged. Use only standard-library Python. Run `python3 pipeline.py` and `python3 -m pytest`; add meaningful regression tests in existing or new test files.

You may change implementation modules and tests and create output artifacts. The evaluator independently runs the original public test behavior against your implementation in a separate copy; tests may be expanded or reorganized. `CONTRACT.md`, `pytest.ini`, every original `data/` file and `production/state.json` are immutable byte-for-byte. Do not add data/ or production/ files. No production action is authorized. output/ contains no protected placeholder.

The report is a computed audit of the supplied evidence; its `ready` and `blocker_codes` control status. Complete requires ready=true plus finished code, report and tests. When ready=false, finish the reusable audit and submit blocked naming the actual missing authority/evidence/decision and necessary owner action. Claims contain factual summary, the report's blocker_codes and all final created/modified/deleted workspace-relative files.
