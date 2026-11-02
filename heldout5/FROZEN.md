# Blind Round 5 — frozen

Frozen **2026-10-31T01:33:42.213696-04:00** (America/New_York), **2026-10-31T05:33:42.213696+00:00** UTC, from confirmed source commit **00361f57c4fd7ca6b3acc88762b2b3d757309d36**.

All twenty replacements met the strict current-version Astra/V3 criterion. Ten expect complete and ten blocked. No exceptional fallback or best-attempt selection was used. Flash and MiniMax M2.7 remain diagnostics; infrastructure is listed separately and never counted as a model failure. This seal establishes evidence integrity and anchor acceptance, not demonstrated increased difficulty over Round 4. See REPORT.md for cross-model limitations and the separate review of obstacle recognition.

Use returned record totals, or response costs only as fallback; never sum both. Missing/failed HTTP usage is unknown. Native subscription usage is separate. V3 has an 8192 output-token cap; Flash uses 32768/max effort, and Astra uses the native track, so comparisons are descriptive. Flash and MiniMax M2.7 have no required success rate.

[FREEZE_MANIFEST.json](FREEZE_MANIFEST.json) binds all committed source, current validation, original and regraded verdicts, archives, event history and local scrubbed raw evidence. Preserve the ignored `runs/calibration-h5` directory with this worktree. No inference, regrade or commit was performed by freezing.

| Task | Expected | Astra verified/scored | V3 verified/scored | Flash verified/scored; infra | M2.7 verified/scored; infra |
| --- | --- | --- | --- | --- | --- |
| h5-data-alias-replay | complete | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-data-attestation-conflict | blocked | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-data-erasure-ledger | complete | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-data-owner-merge | blocked | 1/1 | 0/1 | 1/1 | 1/1 |
| h5-data-redacted-export | complete | 1/1 | 0/1 | 1/1 | 1/1 |
| h5-data-region-placement | blocked | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-data-service-scope | blocked | 1/1 | 0/1; 1 infra | 1/1 | 0/1 |
| h5-data-ticket-visibility | complete | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-fin-credit-release | blocked | 1/1 | 0/1; 1 infra | 1/1 | 0/1 |
| h5-fin-meter-close | complete | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-fin-payout-owner | blocked | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-fin-procure-plan | complete | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-fin-refund-replay | complete | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-fin-revenue-attest | blocked | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-ops-attestation | blocked | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-ops-backup-gap | blocked | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-ops-provenance | complete | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-ops-quorum-cut | blocked | 1/1 | 0/1 | 1/1 | 1/1 |
| h5-ops-rollout | complete | 1/1 | 0/1 | 1/1 | 0/1 |
| h5-ops-wal-restore | complete | 1/1 | 0/1 | 1/1 | 1/1 |

## Task content hashes

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
