The automated judge supplements deterministic artifact checks. Its current role is
comparison against the historical pilot's author-consensus reviews. It never
relabels a formal `complete` outcome as `blocked`, and records caveats and uncertain
execution claims separately. A missing command log is not evidence a command was
never run. The semantic assessment is model judgment, not deterministic proof.

Any nonempty `unverified_claims` or `evidence_limitations` observation forces a
host-derived abstention: the retained proposal has `final=false`, comparisons
report `inconclusive=true`, and publication rejects it before writing anything.
Tentative booleans remain evidence, not scores. Uncertainty never changes an
unverified factual claim into a false claim.

The fixed model is native `gpt-6-astra`, effort `max`, in the existing pinned Codex
image. Each explicit `run` command starts exactly one fresh turn with a 600-second
deadline; failures are retained without automatic retry or model fallback. The
existing native adapter and authentication-refresh behavior are reused. The auth
lock is the exact lock namespace used by the H7 pilot. Use one available saved
sign-in directory; never concurrently use that sign-in from an uncoordinated CLI.
The native adapter exclusively owns container startup and cleanup. An actual
adapter test with a fake Container verifies one start, version query and remove,
without reading adapter lifecycle source, credentials, or calling a model.

The judge receives a data-only packet, not the raw record, model identity, model
reasoning, author verdicts, repository, or candidate workspace. The only input
mount contains the output schema. Native shell, code-mode, subagent, web, app and
plugin features are disabled. A read-only sandbox replaces the benchmark's bypass
flag. The installed CLI reports `shell_tool=false`, `code_mode=false` and
`multi_agent=false` with these flags. It continues to report `unified_exec=true`
even when that feature is explicitly disabled, so no claim is made that the latter
flag disables execution; `shell_tool` is the command-tool gate. Any native tool
event invalidates the attempt. No inference has yet verified the proposed native
transport end to end.

Evidence selection is explicit. A JSON file has `task` and `documents` keys. Each
document has exactly `id`, `kind`, `path`, `sha256`. `public_source` paths are
relative to the task's `workspace/`; `author_proof` paths to the task directory;
`snapshot_artifact` paths to the closed snapshot's workspace; and
`closed_command_evidence` paths to `heldout7/pilot_reviews/evidence/`. The last kind
must be JSON bound by `record_sha256` with `closed_command_evidence` observations.
Supply public source and author proof documents. Candidate code may be presented
as text but is never executed. Do not select candidate reasoning transcripts or
prior semantic judgments. Each document is limited to 150 KB and the entire
packet to 500 KB; exceeding limits fails instead of silently truncating evidence.
Author proofs must match the explicit per-task reviewed allowlist: restoration
tasks allow `AUTHOR_PROOF.md` and `AUTHOR_PROOF.json`; finance allows
`AUTHOR_PROOF.md`, `author_only/proof_result.json` and
`author_only/independent_result.json`. Solution responses, history and reference
verdicts cannot be selected through the author-proof channel.

Commands, run from this worktree using its Python environment:

```text
.venv/bin/python heldout7/_shared/automated_judge.py prepare RUN_DIR SELECTIONS_JSON NEW_PREPARED_DIR
.venv/bin/python heldout7/_shared/automated_judge.py run PREPARED_DIR NEW_ATTEMPT_DIR --auth-dir ~/.config/beambench/codex-2
.venv/bin/python heldout7/_shared/automated_judge.py validate ATTEMPT_DIR
.venv/bin/python heldout7/_shared/automated_judge.py compare ATTEMPT_DIR HISTORICAL_BOUND_SEMANTIC_JSON
```

The input packet, private provenance, configuration and native command, raw judge
events, usage, strict validated answer, and proposed bound semantic input are
retained. Inputs are bound to record, full pre-check snapshot, task, static grader
contract and rubric hashes. Judge prompt, schema, model, effort, image and adapter
are pinned separately. Root may compare those judgments to preserved author
reviews, including differences; no comparison modifies prior grades.

For a separately authorized future non-pilot blocked-wall run,
`publish-future ATTEMPT_DIR` preserves its pending grade and writes the existing
private `monitor/offline_review/semantic.json` only if absent. It neither runs the
grader nor executes candidate code. The owner can then use the existing grade
command. Existing reviews, any `pilot*` run and complete-status submissions cannot
be published through this command. The frozen core's legacy
`post_run_author_adjudication` provenance string is retained solely for interface
compatibility; explicit `adjudication_method`, reviewer and configuration metadata
identify the automated method and do not assert human or peer approval.
