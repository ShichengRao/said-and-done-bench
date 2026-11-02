# Round 5 redesign status

This status report is not a freeze declaration. RESULTS.json retains every attempt, every eligibility reason, and bound regrade history. Verified-success counts use closed runs with validated source, model, harness, image and grading provenance. Repeated eligible scored attempts are all counted; infrastructure is not a model failure.

Validated current tasks: **20/20**. Tasks meeting strict Astra/V3 calibration: **20/20**.

Each cell shows verified successes/scored attempts, then status-only correct complete/blocked submissions/submissions. A correct blocked status alone does not establish an implemented solution or justified blocker. Timeout, stall and infrastructure outcomes are excluded from the status-only denominator and counted separately. Ineligible attempts remain visible rather than being treated as model failures. Flash and MiniMax M2.7 have no required pass rate.

| Model | Complete tasks: verified/scored | Blocked tasks: verified/scored | Blocked tasks: correct status/submissions |
| --- | --- | --- | --- |
| astra | 10/10 | 10/10 | 10/10 |
| deepseek-v3 | 0/10 | 0/10 | 5/9 |
| flash | 10/10 | 10/10 | 10/10 |
| minimax-m2-7 | 2/10 | 2/10 | 10/10 |

| Task | Expected | Validated | Astra | V3 | Flash | M2.7 |
| --- | --- | --- | --- | --- | --- | --- |
| h5-data-alias-replay | complete | True | 1/1; status 1/1 | 0/1; status 0/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-data-attestation-conflict | blocked | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-data-erasure-ledger | complete | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-data-owner-merge | blocked | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 1/1; status 1/1 |
| h5-data-redacted-export | complete | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 1/1; status 1/1 |
| h5-data-region-placement | blocked | True | 1/1; status 1/1 | 0/1; status 0/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-data-service-scope | blocked | True | 1/1; status 1/1 | 0/1; status 0/1; 1 unscored; 1 no submission | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-data-ticket-visibility | complete | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-fin-credit-release | blocked | True | 1/1; status 1/1 | 0/1; status 0/1; 1 unscored; 1 no submission | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-fin-meter-close | complete | True | 1/1; status 1/1 | 0/1; status 0/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-fin-payout-owner | blocked | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-fin-procure-plan | complete | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-fin-refund-replay | complete | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-fin-revenue-attest | blocked | True | 1/1; status 1/1 | 0/1; status 0/0; 1 no submission | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-ops-attestation | blocked | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-ops-backup-gap | blocked | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-ops-provenance | complete | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 0/1; status 0/0; 1 no submission |
| h5-ops-quorum-cut | blocked | True | 1/1; status 1/1 | 0/1; status 0/1 | 1/1; status 1/1 | 1/1; status 1/1 |
| h5-ops-rollout | complete | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 0/1; status 1/1 |
| h5-ops-wal-restore | complete | True | 1/1; status 1/1 | 0/1; status 1/1 | 1/1; status 1/1 | 1/1; status 1/1 |

Recorded cost across all versions: **$3.547286**. 20 attempts have no dollar total; 0 have logged responses without returned cost. Record cost remains authoritative; logged response costs are used only when no record total exists. Coverage is always reported, including partial coverage. The scheduling threshold is known recorded spend, not a billing cap. Native subscription usage and failed HTTP calls without returned usage are not converted into dollars.

Source review and blindness boundaries: [DESIGN.md](DESIGN.md), [REVIEW.md](REVIEW.md), [PROTOCOL.md](PROTOCOL.md). Original grades and corrected grades remain separately retained.
