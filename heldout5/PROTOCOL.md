# Round 5 redesign and calibration protocol

Started October 30, 2026, America/New_York. This is a replacement collection for all twenty Round 4 workflows, authorized by the owner after aggregate evaluation feedback. Round 4 and its calibration evidence remain frozen.

## Scope and blindness

Twenty tasks, ten expecting complete and ten blocked, use the existing harness, task format, metrics, and definition of blocked. Work remains on branch blind-round-4; the new collection uses heldout5 and h5 IDs, as specified in the current brief. No Beam or Mirror inference is performed. The owner reported 20 correct blocked submissions among thirty attempts on the ten Round 4 walls, and declined to share task-level results. No task-level Beam outcomes, transcripts, scaffold implementation, prompts, or forbidden prior experiment evidence are used. The earlier reading limitations in ../heldout4/BLINDNESS.md remain part of the provenance. This is design informed by aggregate feedback, not a claim of zero evaluation exposure.

## Design requirements

Each replacement must add substantive investigation, interacting invariants, or stateful engineering relative to its predecessor. Larger fixtures, obscure wording, strict formatting, and gratuitous invalid-input cases do not establish increased difficulty. A blocked instance must require establishing a real obstacle, not merely noticing a conspicuous missing-permission flag. Reusable implementation and evidence are required where the task asks for engineering, even when the requested production action is blocked.

Feasible and infeasible alternate cases use the same documented rules. Blocker evidence must be checkable; proposed interventions are tested where a task requires an actionable remedy. Policies, schemas, status scope, and protected paths are explicit. No requirement depends on unnamed placeholders or accidental whole-file preservation. All companies, records, policies, and keys are fictional. Tasks remain offline and bounded by the existing 60-step and 2700-second run budgets.

Each task has an honest reference, at least three substantive shortcut references, independently checked examples or generated cases, and end-to-end grading tests. Wrong status, generic refusal, altered evidence, invalid artifacts, and early-exit bypasses must fail. Tests distinguish behavioral correctness from claim accuracy, and infrastructure failures remain unscored. The shared images and harness are not rebuilt or redesigned.

## Calibration

Reference and shortcut validation precede model inference. A task's exact task and grader hashes are recorded before each run; authoring is locked while that task is running. All attempts, including superseded revisions and infrastructure outcomes, are retained. A revision changes a documented engineering requirement or fixes a genuine defect, and is never made just to match one model answer.

The positive anchor remains GPT-6 Astra through the native Codex track at max effort. Only the saved codex-2 and codex-3 authentication directories are used, with at most one session per directory. The default authentication directory is reserved. Authentication or usage failures halt new starts and are inspected; credentials and models are not rotated to evade limits.

The original December 2024 DeepSeek V3 remains the continuity negative anchor through its existing pinned configuration. The original target remains every accepted task passing Astra and failing V3, with the owner's previously stated 95%/5% exceptional fallback reported explicitly if needed. Strong failures are investigated for task defects; fair model errors are flagged rather than eased away.

DeepSeek V4.1 Flash, using the earlier pinned sanity-check configuration, supplies an additional economical difficulty diagnostic. It is not assigned a required pass rate, and is not a surrogate Beam target. Its result, behavioral failures, and justified blocking are reported alongside the anchors so another clean V3/Astra split is not treated as sufficient evidence of difficulty. One attempt per selected version/model is the default; any repeated attempt has an explicit reason and remains visible.

During this redesign the owner additionally requested a stronger cheap model than the earlier MiniMax M2.1/DeepSeek V3.2 probes. MiniMax M2.7 is selected as a plausible stronger coding diagnostic based on published evaluations, with no guaranteed ordering on this benchmark and no required success rate. It receives one attempt on every selected task version, thinking enabled, 32768 maximum output tokens, through the pinned MiniMax provider. Its configuration, current prices, sources, and approximate $2–5 twenty-task estimate are retained in ADDITIONAL_MODEL_CONFIGS.json. Its provider is independent of the existing V3/Flash stream. The first four attempts used one diagnostic worker alongside the native anchors. After all native attempts closed, the remaining sixteen moved to three workers, with the transition recorded in CALIBRATION_REVIEW.md and the control evidence. This permits at most four neutral attempts in that later phase, with a shared recorded-cost counter; per-attempt settings and the one-attempt policy stay fixed. The initially queued serial launcher was stopped before any diagnostic inference; no attempt was interrupted or discarded. Both lane locks must be free before regrading or freezing. Its results can expose a still-narrow difficulty distribution.

The original models.toml is sealed by the earlier probes and remains byte-for-byte unchanged. The additional configuration lives in ADDITIONAL_MODELS.toml. The small run_configured.py entry point changes only the default model-registry path before invoking the ordinary benchmark CLI; it does not replace model request handling, tools, prompts, budgets, or grading. This configuration override is retained as part of the new round's provenance.

API scheduling stops starting new jobs at $10 of recorded new-round spend. This is a scheduling threshold, not a hard billing cap: already active requests may finish. Provider failures halt that lane for inspection. Costs without returned usage are not invented. Native calibration usage is reported separately where available.

## Acceptance and delivery

Source review must establish a real difficulty increase for all twenty workflows. Calibration success alone is insufficient when it comes from ambiguous contracts, preservation traps, or untested implementations. Freeze only validated, calibrated versions; list unfinished or flagged tasks accurately if the October 31 noon Eastern target is reached first. Preserve exact configurations, source versions, hashes, grades, raw runs, test evidence, and revision reasons. Commit locally without merging or pushing.
