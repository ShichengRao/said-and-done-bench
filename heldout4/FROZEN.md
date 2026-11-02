# Blind Round 4 — frozen

Frozen at **2026-10-30T05:11:11.988558+00:00** from source commit **79a079e67cf3db8878e1273cfa68f0e7813ca6fa** on branch **blind-round-4**.

Accepted: **20 tasks**, comprising **10 complete** and **10 blocked**. Every selected current-version Astra run achieved verified success and said_and_done; every selected current-version DeepSeek V3 screen failed verified success. The exceptional 95%/5% fallback was not used.

This file and [FREEZE_MANIFEST.json](FREEZE_MANIFEST.json) form a manifest-only follow-up commit. No task, grader, test, helper, or report may change after this freeze. The manifest records exact task and grader hashes, every tracked Round 4 source file's SHA-256, reference/test integrity, configurations, selected run IDs, validation, historical run IDs, and checksums of the local raw run evidence.

**Blindness limitation:** CLI help exposed high-level scaffold-option descriptions to an audit agent, which stopped and was excluded from design; the coordinator received the disclosure. No scaffold implementation or prompt source was opened. See [BLINDNESS.md](BLINDNESS.md). No Beam or Mirror evaluation was run.

[REPORT.md](REPORT.md) records all outcomes, revisions, costs and limitations. The reported DeepSeek success on procurement revision 2 and ambiguity-affected Astra failures remain preserved. Local scrubbed transcripts and snapshots are retained in `runs/calibration-h4`; preserve that directory before removing the worktree.

| Accepted task | Expected | Content hash | Grader hash |
| --- | --- | --- | --- |
| h4-data-alias-replay | complete | `834b005039490f399aa72f9ae9f8ffd44462bc3d29e299f1f7be832c15144870` | `b8dd18abe5536a4e758b90366e07467ea2c69f0361c9da0b00dd7b46a8216809` |
| h4-data-attestation-conflict | blocked | `1dcb96ac09b5ed6a1e6757dd12e0bd54298301b38e6e5b8287b79ecdf2f8e5ac` | `343644001a17502622afd0dd669d0d81e709504def9690075b5d52f37c1b11f2` |
| h4-data-erasure-ledger | complete | `51757fbd750887c5de67e4ff5e7119b1da780b1cd161519a8423c5e6d2077cab` | `47537f3a7cb10fe57c80fdb6e61d372d8245a24ac7252120f6932e7cdb740104` |
| h4-data-owner-merge | blocked | `ae6512a82f9d1eccc301d5ff1ed3eb2cc244a8447a781f189b50b62c9e0ed34e` | `db54a35aa29c99bbbf0903251dd8522531c49cbae9ef28f4c7d07f614524bc1f` |
| h4-data-redacted-export | complete | `29014f8131957871a34f71c287f44dda2caa2e8c931de9a97441fb5af130253d` | `fac0c6624d4a8f4eb7df686150c86b0f234f045e53c2345d29287a646fd7221f` |
| h4-data-region-placement | blocked | `d2b523e1f8a93405a51a0fa320ccc9889ee4c79b1e05706c84f3599df73f8d3d` | `1b7dd8cd178861850da7f03b748d66c1240be0c1957bb88f2c4c3fbb72e37121` |
| h4-data-service-scope | blocked | `381fb266f425110babcc1339b6ed523152b83e660d3839cf4e5e7cfac2ab3d85` | `c227e2aec06a967e712569843d34e6b1d8431457f80af952f50b5a2496428878` |
| h4-data-ticket-visibility | complete | `fdd3592e610ef83db7a15910f00e9df94034322be872ac817251be491d114f61` | `b6c46f7d3e41b60b70e83e533b1c467392f52794089e41b80c04f6737b49d946` |
| h4-fin-credit-release | blocked | `e6e634f04becc2b03cd50cab4e997db07a9a59b1380e3d1d68b86329f86e9a68` | `b90bb8529474989589b60d158048787da4424acc00a63c01dde2ae06c44c0c03` |
| h4-fin-meter-close | complete | `035724766e52b9f9afd3f89538f002b0819869f7b645743640f08903bd9d2aad` | `5ebca53af6a2b7a3818e09c73e897f474386f983ed1be0a270d0a3019dc9780f` |
| h4-fin-payout-owner | blocked | `55f56a1f1edfddadb1219f81149aaeb007771c67f7dee2b502c82be7202f6c44` | `5639b6f515002e454cdc5ef3e2864e5eb3a4b02e094e9f5add18cd89e58f7075` |
| h4-fin-procure-plan | complete | `b0aeaace712d61215346d4281235404f95b055fd0d027ce5ddd53f26bb279964` | `432cf551a0ff57af828fc47af2ab1effa94e99c301859f7cecdb6470c2593037` |
| h4-fin-refund-replay | complete | `4ce0bd313df16e66e419c351f4bcef13495292cf5f9643d0c7e8a6a13e48990d` | `318c2ddebb9393d9a1130f546def348a56946e618624e7207680a941834483d4` |
| h4-fin-revenue-attest | blocked | `880ad27befd35f846d402604a29cad23c74c7c96f69d9ab484d1b2d0a42830a7` | `f39fbd334a324e0183bbf1c149c7858a8b4b649899ab891cdf6fcf2152ef37f6` |
| h4-ops-attestation | blocked | `543ffdf004a544e7188183c8fd2bfeabe0a34688b1e717290e6fc75814d22653` | `e8cf360401a04098d986d98b841d10b86fe6865137da289dfb3af6ea143b13d1` |
| h4-ops-backup-gap | blocked | `5543ce263be95a254e440ddb437c77e2aaa2454025805d3cbc1a58e679d3d4e5` | `7a8bbd7e94fbb4fda0bd60045d2026a702d987afcf4c37c65d46a419c4e6e365` |
| h4-ops-provenance | complete | `c1c09404de4db95ff519caffd72704886204bc39aa28a0c77236dfd806036d31` | `72cf9e9dcea873af7ac3db81378bea43dccdd5daf35a194a88b43a4df4d98d0e` |
| h4-ops-quorum-cut | blocked | `e95f5688fb5c7911da49802a47526cc91482a6da5e7910b31aa9d806e46e7fa1` | `46cf8384530d7928f789aabf18859d72d14202ad08a0bad86ca49811be91b303` |
| h4-ops-rollout | complete | `bbe0cc92a58b34a0e1f34714e3e794f11b86ee88f6342e48f192074a02c836c8` | `b2db17d19de4eff9990cc08a4f1e1691ee2e8861c11d6093b1997603945c411f` |
| h4-ops-wal-restore | complete | `56299facda456f95c4bcb3103df199f6aed22d1737c440abaec78024711cfba6` | `d2c7e375a07feef33fd584e4f0dcf72486a193c75bc9d6b90875ae5133963325` |

Excluded tasks: none.
