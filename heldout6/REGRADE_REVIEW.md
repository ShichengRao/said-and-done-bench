# Preserving H6 regrade helper review

Prepared October 31, 2026. This helper has not been used on any real run. It launches only the unchanged benchmark `grade` command, never inference. Only explicitly named closed run directories can be targeted; changed inference inputs require a new version, not a regrade.

## Safety model

The default requires exclusive `scheduler.lock` and `diagnostic.lock`. The regular scheduler lock is always exclusive, including the opt-in mode below. Target records must be terminal, have ordered start/end times, frozen snapshot writers, exactly one matching scheduler start/finish, and recorded scheduler completion. The original record and grade bytes are bound to the finish-event hashes. The task input hash must still match the inference record; the current grader and external test must match successful unchanged-source validation, including its historical JSON, log and XML.

An explicitly authorized `--allow-unrelated-diagnostic --diagnostic-tasks ...` mode permits the existing M2.7 scheduler to keep running on a declared disjoint queue. **The operator controls scheduler launches, declares the complete active/remaining queue, and must not launch another diagnostic batch until regrade returns.** The scheduler has no per-task lock, so this operator guarantee is part of the safety model rather than a claim of universal cross-process exclusion. The helper rejects any live/unfinished attempt for a target task, or live work outside the declared M2 queue, before and after each grade. If the diagnostic lock becomes free, it acquires it. No unrelated process command lines or transcript contents are inspected.

Every regrade creates an exclusive grade-history directory containing the exact prior grade, `started.json`, the grade-command log, the exact resulting grade and `event.json`. The benchmark command updates the current `grade.json` only after the original bytes have been retained. All other raw run files are hashed before and after; records, model logs, transcripts and snapshots are never intentionally modified. Current sources, validation, baseline seals and scheduler-event prefix are rechecked. Failed checks preserve the result as a failed event; interrupted/orphan history or failed prior regrades require review and are never automatically retried.

The final appended event remains `event: regrade`, with the fields already consumed by H6 `freeze.py` and `summarize.py`: run/revision identity, before/after grade hashes and flags, source archive, validation/test hashes, raw evidence hashes and history directory. Additional start/end timestamps, log/start-file hashes and diagnostic-policy declaration are retained. `started.json` is local; only the final regrade event is appended to the shared event log, using one append write.

## Controlled-run command

Run only after the two Astra targets close, the regular scheduler records completion and releases its lock, and the repaired graders have fresh valid validation. The currently declared unrelated diagnostic queue is shown explicitly below; revise that declaration if the actual controlled queue changes before execution.

```sh
.venv/bin/python heldout6/_shared/regrade.py \
  h6-ops-attestation/v1-astra \
  h6-ops-attestation/v1-deepseek-v3 \
  h6-ops-backup-gap/v1-astra \
  --reason 'Remove undisclosed conftest rejection while preserving isolated trusted baseline and hidden checks. Grader/test-only fairness repair; inference inputs unchanged.' \
  --allow-unrelated-diagnostic \
  --diagnostic-tasks \
  h6-data-attestation-conflict h6-data-owner-merge \
  h6-data-region-placement h6-data-service-scope \
  h6-fin-credit-release h6-fin-payout-owner h6-fin-revenue-attest \
  h6-data-alias-replay h6-data-redacted-export h6-data-erasure-ledger
```

For a fully idle run, omit both diagnostic options and use the stricter default. Supplying the flag without the complete declaration, or declaring any target task, is rejected.

## Validation and hashes

Forty temporary-fixture tests passed with zero failures, errors or skips; no Docker, inference or actual run grading was invoked. Tests cover exact archive/event retention, repeated explicit regrades, raw/source/validation identity failures, closed infrastructure outcomes, malformed grader output, regular/diagnostic locks, disjoint ongoing work, forbidden target activity, activity arriving during grading, orphan/failed history and freezer-compatible fields. Sources were unchanged during the retained check.

Evidence: `validation/REGRADE_HELPER_TESTS.json`, `.log`, and `.xml`.

| File | SHA-256 |
|---|---|
| `_shared/regrade.py` | `70a240bb552cc41891e0f2325c236d23c4440e98cfb14c2a783ca16b3594046b` |
| `_shared/test_regrade.py` | `43b6abdc4fa865dc4263fbc8e8c98cfcd3c3b16c1c328c4ad5e2f08d1624490b` |
| `validation/REGRADE_HELPER_TESTS.log` | `cde7bcb81d2c9cb5229f32ce18e2755ef158cbbff7dd9387bfcce14502c91c25` |
| `validation/REGRADE_HELPER_TESTS.xml` | `67d02ea4a2cc913b0a4a4a0c15274ed4cae791e54e1e2c3383d62bd77b45e06b` |

No runtime-pinned scheduler/configuration/validation helper, task, grader, prior evidence or model setting was changed by this helper work. No commit or regrade was performed.
