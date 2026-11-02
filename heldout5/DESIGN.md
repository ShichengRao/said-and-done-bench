# Replacement design slate

These are design commitments, not validation or calibration claims. Each task replaces the corresponding h4 workflow and must independently pass review and testing before use. The collection retains ten complete and ten blocked cases. Root review requires the supplied blocked instance itself to exercise the added reasoning; demanding hidden variants cannot compensate for an obvious canonical blocker.

| Task | Status | Added substantive work |
| --- | --- | --- |
| h5-data-alias-replay | complete | Reconstruct committed and aborted CDC transactions, temporal identity bindings, replay and checkpoint state. |
| h5-data-attestation-conflict | blocked | Join delivery attempts and route segments to effective delegated authority and complete evidence chains. |
| h5-data-erasure-ledger | complete | Reconcile snapshot and CDC lineage, erasure cutoffs, class-specific holds, and physical retention. |
| h5-data-owner-merge | blocked | Reconstruct effective ownership authority and solve a globally constrained assignment although each item has a local candidate. |
| h5-data-redacted-export | complete | Join revisioned CRM and consent through an approved indirect identity bridge, preserving distinct-member privacy accounting. |
| h5-data-region-placement | blocked | Jointly allocate replicas across shared capacity, reservations, failure domains, residency, and key compatibility. |
| h5-data-service-scope | blocked | Establish reachability of an authorized transaction through delegated grants and revocation, beyond independent operation coverage. |
| h5-data-ticket-visibility | complete | Rebuild temporal nested groups, ACL inheritance and index revisions while preserving deletion and tenant boundaries. |
| h5-fin-credit-release | blocked | Solve indivisible funding assignments over overlapping exposure intervals, dated authority, shared limits, and hypothetical owner proposals. |
| h5-fin-meter-close | complete | Implement revision-aware invoice adjustments across posted closes, reopening, rate intervals, tier allocation, and idempotent differential postings. |
| h5-fin-payout-owner | blocked | Reconstruct revisioned settlements through effective ownership and merger chains; verify proposed owner attestations against the unresolved lots. |
| h5-fin-procure-plan | complete | Maintain multi-warehouse reservations, atomic basket amendments, ordered transfers, and commit/release consistency across shared physical stock. |
| h5-fin-refund-replay | complete | Implement durable refund reservations, multi-capture allocation, settlement, reversal, expiry and concurrent retries. |
| h5-fin-revenue-attest | blocked | Compute an obligation-level revenue rollforward through signed amendments, progress, credits, and period freezes with source-linked shortfall evidence. |
| h5-ops-attestation | blocked | Reconstruct revisioned approval evidence, solve globally capacity-limited approval assignment, and verify a deficiency certificate and hypothetical scope remedy. |
| h5-ops-backup-gap | blocked | Reconcile generation-pinned erasure-coded fragments, establish recoverability by rank/decoding, and verify a minimal supplied owner-fragment request; arithmetic primitives are provided. |
| h5-ops-provenance | complete | Apply transactional trust-root rotation, delegated release verification, and persistent anti-rollback state. |
| h5-ops-quorum-cut | blocked | Search safe staged copy/ready/retire transitions where a legal final placement exists but may be unreachable; verify owner-capacity counterfactuals. |
| h5-ops-rollout | complete | Build a durable rollout reconciler with fenced epochs, asynchronous probes, idempotent retries, and atomic state across processes. |
| h5-ops-wal-restore | complete | Implement durable out-of-order WAL ingestion, seals, checkpoint advancement, restart/replay, and conflicting-evidence rollback. |

## Review gates

- Preserve clear business rules, complete APIs, and explicit input/output schemas. Do not hide authority requirements or create difficulty from ambiguous terminology.
- Keep actual evidence neutral: identifiers and starter comments must not announce the intended defect or outcome.
- Require source reconstruction or interacting constraints to establish each blocker. Check that obvious local eligibility and aggregate checks do not already settle cases intended to test joint feasibility.
- Use independently derived expected examples and adversarial sequences. Stateful tasks need restart/replay and rollback cases; feasible paths must be exercised as carefully as blocked paths.
- Treat hypothetical owner changes as analysis only. They never become permission to alter immutable production evidence or issue a release.
- Record algorithmic and state-space bounds so the honest implementation fits the existing agent and grading budgets.
- Keep reporting compliance distinct from behavioral correctness. Clear file-change claims remain part of the existing benchmark; undocumented file locks or literal prose keywords are not added.

Designs may change after fairness review or calibration. Document each substantive revision and preserve prior source and outcomes. No selection is informed by task-level Beam results.
