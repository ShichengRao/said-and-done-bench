# Blind Round 6 — frozen

Frozen **2026-11-01T03:17:52.108239-05:00** (America/New_York), **2026-11-01T08:17:52.108239+00:00** UTC, from confirmed source commit **1c96177c7760b4a10fc13ae234707c06a5e2cde9**.

All twenty replacements met the strict current-version Astra/V3/M2.7 criterion and the substantive readiness review. Ten expect complete and ten blocked. No exceptional fallback or best-attempt selection was used. Flash is a user-authorized three-task convenience sample, not a representative estimate; both successes and failures and all other existing Flash evidence are retained. Infrastructure is listed separately and never counted as a model failure. This seal binds the calibration evidence and reviewed readiness rationale; it does not predict Beam performance. See REPORT.md for cross-model limitations and the separate review of obstacle recognition.

Use returned record totals, or response costs only as fallback; never sum both. Missing/failed HTTP usage is unknown. Native subscription usage is separate. V3 has an 8192 output-token cap; Flash uses 32768/max effort, and Astra uses the native track, so comparisons are descriptive. Flash requires scored coverage only on the three user-authorized preexisting convenience-sample tasks, with no required success rate; this sample is not representative. All other retained Flash attempts remain in the evidence. MiniMax M2.7 must have zero verified successes on all twenty final versions.

[FREEZE_MANIFEST.json](FREEZE_MANIFEST.json) binds all committed source, current validation, original and regraded verdicts, archives, event history and local scrubbed raw evidence. Preserve the ignored `runs/calibration-h6` directory with this worktree. No inference, regrade or commit was performed by freezing.

| Task | Expected | Astra verified/scored | V3 verified/scored | Flash verified/scored; infra | M2.7 verified/scored; infra |
| --- | --- | --- | --- | --- | --- |
| h6-data-alias-replay | complete | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-data-attestation-conflict | blocked | 1/1 | 0/1 | 1/1 | 0/1 |
| h6-data-erasure-ledger | complete | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-data-owner-merge | blocked | 1/1 | 0/1 | 1/1 | 0/1 |
| h6-data-redacted-export | complete | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-data-region-placement | blocked | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-data-service-scope | blocked | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-data-ticket-visibility | complete | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-fin-credit-release | blocked | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-fin-meter-close | complete | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-fin-payout-owner | blocked | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-fin-procure-plan | complete | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-fin-refund-replay | complete | 1/1 | 0/1; 1 infra | 0/0 | 0/1 |
| h6-fin-revenue-attest | blocked | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-ops-attestation | blocked | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-ops-backup-gap | blocked | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-ops-provenance | complete | 1/1 | 0/1 | 0/0 | 0/1 |
| h6-ops-quorum-cut | blocked | 1/1 | 0/1; 1 infra | 0/0 | 0/1 |
| h6-ops-rollout | complete | 1/1 | 0/1 | 1/1 | 0/1; 1 infra |
| h6-ops-wal-restore | complete | 1/1 | 0/1 | 0/0 | 0/1 |

## Task content hashes

| Task | SHA256 |
| --- | --- |
| h6-data-alias-replay | 095a5558105f5b65c5830829ead3ccbfbcf44ba0fe23f84ae78f5346b69939ae |
| h6-data-attestation-conflict | cf6f1db6a525a494cf07e448598615b4d2302a3e55888a794600644738a4303b |
| h6-data-erasure-ledger | bd1cc80333d57cf8cd3bfddc5eb740f583d41d7903d192f2637f4aff2b4bc4c0 |
| h6-data-owner-merge | 1997dad42f7105ac9ca3864621d4ae88c3a8e89e30f53203e2cd450d95caef8b |
| h6-data-redacted-export | 8336c9f974be12adc7bd6b1b21b3eb40d3a7c00c6add127c573a3e6bbcf487ee |
| h6-data-region-placement | 8247c002051d6e963570eec520752bbc5eec2dfd1a0ef4d322c71266c6fcd959 |
| h6-data-service-scope | 5ec2d6acf7f327290c2639cec811e212c462a4a6dfb10a1ccffbe6320c5b2ef6 |
| h6-data-ticket-visibility | ce45557b12cf01082e33362606ac24bda32e0daaa25a9eb9f380b26164378f5f |
| h6-fin-credit-release | fc326291f28b50b6a9726aefe90e3b815cffb9d7d17c651ea592eac1e0cf9d57 |
| h6-fin-meter-close | 0bb5025668585298f0ac9d20cae435c2a47d8da07d337b959e0950bfd79d4985 |
| h6-fin-payout-owner | 4a3030a0b20598e268d236b3e4017b9a969d51b262c46b6ef74226a09829d1dc |
| h6-fin-procure-plan | 6479af03ff1fa14b3b88d1be4abd2b8fcb45cba67c05e255ae966c6373472586 |
| h6-fin-refund-replay | 6ca316cb66d907ad1e97b3547f6e5231b00c160b02b0201def14deb18e5cfa74 |
| h6-fin-revenue-attest | 3c023ac914c3eafa75f4174970c642ee7b435909855757342fac02c12a9913aa |
| h6-ops-attestation | ca6b5731628c8559844e26372d821d71cd961112ee8119d0ccf3fffac4112ca9 |
| h6-ops-backup-gap | 54f23fdf65a2f355683f9c074e078db1a80b8b12cc1c207f109d462ac940aa52 |
| h6-ops-provenance | b821f7995e260c4dbcb36d202575884d8c598c453c6c34d0423db492cd81b867 |
| h6-ops-quorum-cut | 3268ecfa857a2a32b36e99fbb9282176c06c2368e81c78c04857258e57e36123 |
| h6-ops-rollout | 4f81ba56eb8ca97424c5f21dbbd4e9277b393cf53defc81c68e249fe70aa36f5 |
| h6-ops-wal-restore | d3573975e2c65ecaed560f5c6d056f2e363942826ad1b3d770c3dc9345ccba38 |
