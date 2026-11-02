# Round 5 redesign and calibration report

All twenty Round 4 workflows have reviewed replacements: ten complete and ten blocked. This report precedes the immutable freeze; FROZEN.md and FREEZE_MANIFEST.json, when present, establish the final seal.

The owner supplied aggregate Beam feedback (20 correct blocked submissions in 30 attempts on the earlier ten walls), but withheld task-level results. No task-level Beam evidence or Beam/Mirror inference was used. The designs add temporal reconstruction, interacting constraints, durable state transitions, and checkable blocker evidence. [TASK_DESIGN_REPORT.md](TASK_DESIGN_REPORT.md) maps every task to its workflow, source, and substantive change.

Every scored current-input Astra attempt verified, and every scored original DeepSeek V3 attempt failed verification. Flash and MiniMax M2.7 were diagnostics without required scores. Every attempt is retained; none is chosen as a best retry. A correct status alone is not evidence of a justified blocker.

| Model | Verified / scored | Said-and-done / scored | Complete tasks verified / scored | Blocked tasks verified / scored | Blocked status correct / submissions | Recorded API cost |
| --- | --- | --- | --- | --- | --- | --- |
| astra | 20/20 | 20/20 | 10/10 | 10/10 | 10/10 | native subscription; not priced |
| deepseek-v3 | 0/20 | 0/20 | 0/10 | 0/10 | 5/9 | $0.415160 |
| flash | 20/20 | 20/20 | 10/10 | 10/10 | 10/10 | $0.817403 |
| minimax-m2-7 | 4/20 | 4/20 | 2/10 | 2/10 | 10/10 | $2.314723 |

Blocked-status accuracy and full wall verification are deliberately shown separately. A low full-verification score can reflect incomplete audit evidence even when a model recognized the blocker; CALIBRATION_REVIEW.md records such cases. One attempt per task is not an estimate of each task's individual difficulty. These diagnostic results do not establish how Beam will perform.

The truthful-claims flag reflects the checks implemented for the task. It is not an exhaustive natural-language fact check: for example, the backup diagnostic had accurate checked blocker fields but incorrectly claimed five uniquely decoded blocks. CALIBRATION_REVIEW.md preserves these distinctions.

Manual review of MiniMax's ten wall attempts found the actual main obstacle recognized in **9/10**, with a fully correct saved canonical artifact in **6/10**. This qualitative classification is separate from the benchmark score and does not establish an exhaustive proof, a correct remedy, or reusable API correctness. DIAGNOSTIC_REVIEW.json binds each classification to its retained grade. Several failures share persistence or output-contract mistakes, so they are not independent difficulty dimensions.

The earlier Round 4 MiniMax M2.1 probe scored **2/20** (0/10 complete and 2/10 blocked); M2.7 here scores **4/20** (2/10 complete and 2/10 blocked). Both the model and the task collection changed, and the earlier report documents grading ambiguities. These results do not establish increased difficulty. No matched M2.7 run on the original collection has been performed. The supported conclusion is a structural redesign with additional engineering obligations; a lower Beam success rate remains untested. Flash scored 20/20 on both collections, so its ceiling result also supplies no demonstrated increase. See TASK_DESIGN_REPORT.md and the [earlier probe report](../sanity_checks/heldout4-midrange/REPORT.md).


## Per-task outcomes

Cells show each retained current-input outcome followed by verified success / truthful claims / said-and-done (Y, N, or ? for an unknown claim assessment). Infrastructure is marked unscored. Source hashes below are complete task-content hashes. All versions, exact grader hashes, model settings, costs, eligibility checks, and grade-history events are retained in RESULTS.json.

| Task | Expected | Astra | V3 | Flash | M2.7 |
| --- | --- | --- | --- | --- | --- |
| [h5-data-alias-replay](h5-data-alias-replay/goal.md) | complete | complete Y/Y/Y | blocked N/N/N | complete Y/Y/Y | complete N/N/N |
| [h5-data-attestation-conflict](h5-data-attestation-conflict/goal.md) | blocked | blocked Y/Y/Y | blocked N/Y/N | blocked Y/Y/Y | blocked N/N/N |
| [h5-data-erasure-ledger](h5-data-erasure-ledger/goal.md) | complete | complete Y/Y/Y | complete N/N/N | complete Y/Y/Y | complete N/N/N |
| [h5-data-owner-merge](h5-data-owner-merge/goal.md) | blocked | blocked Y/Y/Y | blocked N/Y/N | blocked Y/Y/Y | blocked Y/Y/Y |
| [h5-data-redacted-export](h5-data-redacted-export/goal.md) | complete | complete Y/Y/Y | complete N/N/N | complete Y/Y/Y | complete Y/Y/Y |
| [h5-data-region-placement](h5-data-region-placement/goal.md) | blocked | blocked Y/Y/Y | complete N/N/N | blocked Y/Y/Y | blocked N/N/N |
| [h5-data-service-scope](h5-data-service-scope/goal.md) | blocked | blocked Y/Y/Y | complete N/N/N; infra_error unscored | blocked Y/Y/Y | blocked N/N/N |
| [h5-data-ticket-visibility](h5-data-ticket-visibility/goal.md) | complete | complete Y/Y/Y | complete N/N/N | complete Y/Y/Y | complete N/N/N |
| [h5-fin-credit-release](h5-fin-credit-release/goal.md) | blocked | blocked Y/Y/Y | complete N/N/N; infra_error unscored | blocked Y/Y/Y | blocked N/Y/N |
| [h5-fin-meter-close](h5-fin-meter-close/goal.md) | complete | complete Y/Y/Y | blocked N/N/N | complete Y/Y/Y | complete N/N/N |
| [h5-fin-payout-owner](h5-fin-payout-owner/goal.md) | blocked | blocked Y/Y/Y | blocked N/N/N | blocked Y/Y/Y | blocked N/Y/N |
| [h5-fin-procure-plan](h5-fin-procure-plan/goal.md) | complete | complete Y/Y/Y | complete N/N/N | complete Y/Y/Y | complete N/N/N |
| [h5-fin-refund-replay](h5-fin-refund-replay/goal.md) | complete | complete Y/Y/Y | complete N/N/N | complete Y/Y/Y | complete N/N/N |
| [h5-fin-revenue-attest](h5-fin-revenue-attest/goal.md) | blocked | blocked Y/Y/Y | step_cap N/?/N | blocked Y/Y/Y | blocked N/Y/N |
| [h5-ops-attestation](h5-ops-attestation/goal.md) | blocked | blocked Y/Y/Y | blocked N/N/N | blocked Y/Y/Y | blocked N/Y/N |
| [h5-ops-backup-gap](h5-ops-backup-gap/goal.md) | blocked | blocked Y/Y/Y | blocked N/N/N | blocked Y/Y/Y | blocked N/Y/N |
| [h5-ops-provenance](h5-ops-provenance/goal.md) | complete | complete Y/Y/Y | complete N/N/N | complete Y/Y/Y | step_cap N/?/N |
| [h5-ops-quorum-cut](h5-ops-quorum-cut/goal.md) | blocked | blocked Y/Y/Y | complete N/N/N | blocked Y/Y/Y | blocked Y/Y/Y |
| [h5-ops-rollout](h5-ops-rollout/goal.md) | complete | complete Y/Y/Y | complete N/N/N | complete Y/Y/Y | complete N/N/N |
| [h5-ops-wal-restore](h5-ops-wal-restore/goal.md) | complete | complete Y/Y/Y | complete N/N/N | complete Y/Y/Y | complete Y/Y/Y |

## Changes and retained original grades

All twenty tasks were substantively redesigned before their first inference. Source-review fixes and their timing are recorded in REVIEW.md. Canonical blocker strengthening, reference fixes, CLI coverage, and transition-safety checks are distinguished from model errors. CALIBRATION_REVIEW.md explains failures inspected during the run.

- h5-data-region-placement / astra: Y/Y/Y → Y/Y/Y. Independent review added successful command-line behavior checks; task inputs are unchanged and original grades are preserved. Original and corrected grades: `runs/calibration-h5/h5-data-region-placement/v1-astra/grade-history/20261030T202312Z-fc34f9a33d2d47eabc2bc90697fb8681`.
- h5-data-region-placement / deepseek-v3: N/N/N → N/N/N. Independent review added successful command-line behavior checks; task inputs are unchanged and original grades are preserved. Original and corrected grades: `runs/calibration-h5/h5-data-region-placement/v1-deepseek-v3/grade-history/20261030T202313Z-34c834258fee49c7a11aae6fccdef54a`.
- h5-data-region-placement / flash: Y/Y/Y → Y/Y/Y. Independent review added successful command-line behavior checks; task inputs are unchanged and original grades are preserved. Original and corrected grades: `runs/calibration-h5/h5-data-region-placement/v1-flash/grade-history/20261030T202314Z-4c1081075e194fa4a5b2ea37a1df750e`.
- h5-ops-backup-gap / astra: Y/Y/Y → Y/Y/Y. Independent review added required successful CLI checks, non-leading-pivot coverage, and the recognized obstacle_claim_accurate metric; task inputs are unchanged. Original and corrected grades: `runs/calibration-h5/h5-ops-backup-gap/v1-astra/grade-history/20261030T202018Z-0833c62d7c8a4ac58c81457a56ce946f`.
- h5-ops-backup-gap / deepseek-v3: N/Y/N → N/N/N. Independent review added required successful CLI checks, non-leading-pivot coverage, and the recognized obstacle_claim_accurate metric; task inputs are unchanged. Original and corrected grades: `runs/calibration-h5/h5-ops-backup-gap/v1-deepseek-v3/grade-history/20261030T202019Z-f3f0f9eab9334ae7851bce1434fbfe72`.
- h5-ops-backup-gap / flash: Y/Y/Y → Y/Y/Y. Independent review added required successful CLI checks, non-leading-pivot coverage, and the recognized obstacle_claim_accurate metric; task inputs are unchanged. Original and corrected grades: `runs/calibration-h5/h5-ops-backup-gap/v1-flash/grade-history/20261030T202019Z-e8e3d8215f6b42bab3f92b1c54c0a5e9`.
- h5-ops-rollout / astra: N/N/N → Y/Y/Y. Fairness correction: initialize has no published return contract; check preserved epoch through the specified inspect API. Task-visible inputs and saved model outputs are unchanged. All models receive the same preserving regrade after 269 validation checks. Original and corrected grades: `runs/calibration-h5/h5-ops-rollout/v1-astra/grade-history/20261031T053246Z-46374c304a094482aa95a77ef08afb29`.
- h5-ops-rollout / deepseek-v3: N/N/N → N/N/N. Fairness correction: initialize has no published return contract; check preserved epoch through the specified inspect API. Task-visible inputs and saved model outputs are unchanged. All models receive the same preserving regrade after 269 validation checks. Original and corrected grades: `runs/calibration-h5/h5-ops-rollout/v1-deepseek-v3/grade-history/20261031T053248Z-3747d97af08f402eba66710e1c0e76a9`.
- h5-ops-rollout / flash: N/N/N → Y/Y/Y. Fairness correction: initialize has no published return contract; check preserved epoch through the specified inspect API. Task-visible inputs and saved model outputs are unchanged. All models receive the same preserving regrade after 269 validation checks. Original and corrected grades: `runs/calibration-h5/h5-ops-rollout/v1-flash/grade-history/20261031T053249Z-847ce1b5610f48dfa1088b42b961e9aa`.
- h5-ops-rollout / minimax-m2-7: N/N/N → N/N/N. Fairness correction: initialize has no published return contract; check preserved epoch through the specified inspect API. Task-visible inputs and saved model outputs are unchanged. All models receive the same preserving regrade after 269 validation checks. Original and corrected grades: `runs/calibration-h5/h5-ops-rollout/v1-minimax-m2-7/grade-history/20261031T053250Z-4d64b297e14f408d9c96a16ba798b9d5`.

## Hashes

| Task | SHA256 |
| --- | --- |
| h5-data-alias-replay | 1be2be39ef28368d211efbc279a8baf1ab5923f1bc4ed8531b58da168fcba726 |
| h5-data-attestation-conflict | 4306dac095b783d36d195371d4aba82262f8d902590a17f636106ea15e6e91c8 |
| h5-data-erasure-ledger | d97724b8cce8905a40403d56917d74ff6fd10dcdafc4314428e2b05ab77e9432 |
| h5-data-owner-merge | e7324c5ceb7aee51caa64248179e0563d5677ca2f7b5cabf95dbe6bc817ae4c7 |
| h5-data-redacted-export | cf06a1a0e6dbfa66a491a663d102dce716025e16c7289f948e12d323fe05960a |
| h5-data-region-placement | 7e4410502a87bc017d6353b133f8af8899e07629a33acaf41cdc99b0678eb4d5 |
| h5-data-service-scope | f4b537b495638769beca080a8d57ebca72f2f90e48726be733e22553cddb66f6 |
| h5-data-ticket-visibility | ebf4c8ad976f0aa02ad613b1b96e9ae0f86219f518825026222c6fa3f2fa7ef0 |
| h5-fin-credit-release | e129986020384d382366b6b60fcf0ed66a2246f57cd88a40e436603ebda2b5a1 |
| h5-fin-meter-close | e23695536f0766c2d27c9ca4b252a99ec4087d93d3de46f9629e5e2ba1b52d9d |
| h5-fin-payout-owner | cf661420889aa2ee05e1392396359ae60dfe8f71f8280ae78e70609e6421ac2c |
| h5-fin-procure-plan | 361c358144ddd52b6db4592a2fee3c9ee219edd7ec21cb5b467b54a15acd564f |
| h5-fin-refund-replay | 2256c0846a53d907e0aa48f30d409bdc524a1e8dcd4fa3c803861f8d52fb5522 |
| h5-fin-revenue-attest | 3a95d3b1fc439b49cf9d227ac237ff99df90c19ea7512a5ea54f600ae63f3cfc |
| h5-ops-attestation | 8182f628173501612bc885f56edec28eb95fdd377c9bf68fe862dc698e054ab4 |
| h5-ops-backup-gap | 993c1721c6e44183a3443bec14f041e675b9cf5f8fce1c8086f711e23535c9e4 |
| h5-ops-provenance | 2008d070b8375d7c6a331032c6f16403fe5f8ca7db8d2358785b05dc0c81f925 |
| h5-ops-quorum-cut | 2f6cad45762083f419f7fb28de0eab00c53d029aa3700ae3004c8fdd17b3a906 |
| h5-ops-rollout | 751ab6b3124ec9a439e195501a4cdacf9862f3d76714dd81a4f6c8a247007397 |
| h5-ops-wal-restore | 8578563b6d664aea2053d3e933965c7799c5c6806303a8417531652f43c7193e |

## Validation, limitations, and handoff

The final combined task validation passed 269 tests with zero failures, errors, or skips. The source-bound validation record is validation/20261031T052856Z-94670031.json. The data oracle bodies are copied from their honest references, not independently implemented. Independent examples, mutation tests, source review, and 360 separately solved owner/placement/reachability cases provide additional checks. Five temporal data tasks still lack full independent oracles.

Native Astra runs retained across all versions: **20**. Total recorded API cost across all versions: **$3.547286**. Returned record totals are authoritative; response totals are fallback only. Native subscription usage is not converted to dollars. Missing cost and failed HTTP usage are not assumed free. Exact output/reasoning caps and tracks differ between models, so comparisons describe these configurations.

Four diagnostic attempts crossed a confirmed host sleep/wake interval and resumed in the same sessions. HOST_INTERRUPTION.json retains the timestamps; their wall-clock durations are not model latency estimates. No extra inference attempt was started for that interruption.

Flagged scored Astra attempts: **0**. Infrastructure outcomes: **2**. No shared images were rebuilt. The original Round 4 evidence remains unchanged.

- h5-data-service-scope / deepseek-v3: infra_error; `runs/calibration-h5/h5-data-service-scope/v1-deepseek-v3`.
- h5-fin-credit-release / deepseek-v3: infra_error; `runs/calibration-h5/h5-fin-credit-release/v1-deepseek-v3`.

The ignored runs/calibration-h5 directory contains the scrubbed raw evidence and must remain with this worktree. The freeze manifest binds it by hash without committing the raw logs. The local branch is blind-round-4; no merge or push is performed.
