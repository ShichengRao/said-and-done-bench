# Independent readiness-helper review

Reviewed the H6 freezer, summarizer and focused regression gates without running inference, regrading model attempts, or touching runtime-pinned configuration/helpers. The review began read-only. The root coordinator authorized corrections only to freeze.py, summarize.py and their focused tests.

## Findings and fixes

1. The summarizer previously accepted an empty set of returned model/provider identities. It also omitted missing identity fields from those sets, allowing one valid response to hide another response without identity. Scored neutral attempts now require a returned response and complete model/provider identity on every returned response. Empty or partial identity evidence remains visible but ineligible.
2. M2.7 thinking was counted for reporting but was not required in the summarizer or freezer. Both now require at least one returned response with nonempty reasoning, reasoning_content or reasoning_details for non-infrastructure M2.7 attempts. Request-side thinking configuration alone is insufficient.
3. Scheduler start.runtime_sha256 was not checked against the reviewed runtime. Both summary eligibility and freeze verification now require the exact current pinned mapping, including key set and digests. The live calibrator, validation helper, bootstrap and model configuration files were not modified.
4. The summarizer could treat absent or nonboolean verified-success flags as a negative result. It now validates all core grade booleans and nullable claims_truthful, rejects grader-error outcomes as model evidence, requires non-infrastructure closed runs to be scored, and refuses verified infrastructure.
5. A valid failure could previously make a task's strict gate true even with an ineligible attempt on the same task input. Strict gates now reject any same-input ineligible attempt. Older source versions are retained and remain reported; they do not prevent a genuinely revised input from satisfying its own gate. No best-attempt selection was added.
6. Malformed response envelopes, JSON records, choice containers and usage containers now yield explicit summary ineligibility instead of disappearing from coverage or causing an incidental parser crash. Cost coverage remains explicit; missing usage is not zero.

Infrastructure with no returned responses is retained as unscored evidence with zero observed thinking and unknown usage. It is never counted as a model failure. Existing live-response protection remains: open attempt response contents are not inspected by the summarizer.

No additional blocker was found in the reviewed freezer's current-round source inventory, exclusive nonoverwrite output creation, scheduler/diagnostic lock acquisition, double collection comparison, source archive binding, retained-grade chain, or current grade-bound substantive readiness review. The root's corrected H6 test inventory glob and its regression are included. This is a bounded code audit, not proof of all possible tampering resistance, and no freeze was attempted.

## Validation

Command: `.venv/bin/python -m pytest -q heldout6/_shared/test_calibration_helpers.py heldout6/_shared/test_freeze_gates.py --junitxml=heldout6/validation/HELPER_REVIEW_TESTS.xml`

**59 passed; 0 failed, 0 errors, 0 skipped.** Retained stdout is HELPER_REVIEW_TESTS.log and JUnit evidence is HELPER_REVIEW_TESTS.xml. Tests cover empty/partial/wrong identities, actual thinking in all three supported response fields, missing or changed runtime mappings, missing/nonboolean verdicts, current-versus-old input eligibility, empty infrastructure retention, live-response noninspection, missing/mixed anchor scores, and stale/incomplete substantive review bindings.

| Reviewed source or evidence | SHA256 |
| --- | --- |
| _shared/freeze.py | 419594f6cfc2f4e657f3f341f3e47f5c2cd679986358e2e10338a09cec484a99 |
| _shared/summarize.py | 988e19f28a2b7e0ecc3969de6c2b53612202abbeda815430600fd30585fb876e |
| _shared/test_freeze_gates.py | d7906e8480dc56dbd485698e8e11125ded8b71199c597af756ba792a60386dac |
| _shared/test_calibration_helpers.py | 71de3e741beb454036ca699d8260945407b6834b23f9e1717a932f5e65282823 |
| validation/HELPER_REVIEW_TESTS.log | b687790dea2002642b08cfae52fc579efa13a82265fc1ccca6785fda7fb0a302 |
| validation/HELPER_REVIEW_TESTS.xml | 478e0d475cc8627673de84bc3482f916ca958e834e9d81f1e2b4985d0af6e4b0 |
