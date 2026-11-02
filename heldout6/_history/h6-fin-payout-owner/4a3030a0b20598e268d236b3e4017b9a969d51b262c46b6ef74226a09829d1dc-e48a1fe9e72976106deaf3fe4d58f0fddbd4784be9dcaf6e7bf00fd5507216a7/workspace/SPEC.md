# Payout dispatch, delayed provider receipts and reusable bridge leases

Implement `settlement.analyze(bundle)` and `python3 settlement.py data/request.json`, printing the returned JSON. Work on other valid bundles without mutating inputs. SPEC.md and data/ are immutable; code/tests may be added or edited. Original examples are independently rerun. Everything is fictional, offline, integer cents. No interest, fees, deadlines, credit other than listed bridges, or negative balances are allowed.

## Reconstruct current signed authority

Input has `{as_of,wallets,owners,payouts,leases,proposals}`. wallets are unique `{id,balance}`. The other three authority streams contain revisions, arriving in arbitrary order with possible exact duplicates. Every delivery has `{id,revision,known,signed,void}` plus these payloads:
- owners: `{wallet}` binds that owner ID to one wallet.
- payouts: `{source_owner,destination_owner,cents,receipt_after}`; receipt_after is a list of payout IDs whose DISPATCH must have occurred before this payout's provider receipt can be posted.
- leases: `{owner,cents,activate_after,release_after}`; these two lists contain payout IDs whose RECEIPTS must have posted before the lease may be drawn or repaid, respectively.

For EACH stream discard known > as_of, reject nonidentical visible duplicates of `(id,revision)` with ValueError even if unsigned/superseded, then select the highest SIGNED revision per ID. A signed void winner removes that item. Unsigned drafts do not revoke signed authority. All resolved references exist (including in hypothetical options); payout/lease amounts are positive, wallet balances nonnegative, revision positive, known nonnegative. Source and destination resolve to different wallets. Definitions are whole replacements, not patches. Resolve every owner binding before simulating. A future or unsigned authorization cannot be used today.

## Legal execution state

Initially no payout is dispatched/received and no bridge is active. Each payout dispatch and receipt happens at most once. The possible actions are:
- `dispatch:ID`: an undispatched payout may debit cents from its source wallet only if the wallet currently has that much cash. It immediately consumes cash but does NOT yet credit the destination.
- `receipt:ID`: a dispatched, unreceived payout may credit its destination exactly once when every receipt_after payout has been dispatched. No additional cash is required. These are provider release dependencies, not automatic next actions.
- `draw:ID`: if no bridge is active and every activate_after payout has been received, credit this lease's cents to its owner's wallet and make it active. The treasury desk permits only ONE active bridge across all wallets.
- `repay:ID`: the active lease may be debited/released only when its wallet has the cents and all release_after payouts have been received. A released lease may later be drawn again. The same active lease cannot be drawn twice.

All actions are atomic. No partial payout, split bridge, unauthorized overdraft, premature receipt, cancellation, or netting is allowed. A bridge release returns capacity, not additional cash. Completion requires every current payout RECEIVED and no active bridge. Positive final net balances alone do not establish that a legal schedule exists.

For state exploration use the finite state `(dispatched IDs, received IDs, active lease or null)`; balances are uniquely derived from that state. Repeated lease cycles can revisit a state and add no reachability. The initially reachable state counts. Search all reachable states, retaining the shortest action sequence to each state and lexicographically smallest sequence among equal lengths. Action strings compare by ordinary ASCII ordering.

## Returned evidence and hypothetical owner review

Return exactly `{requested_cents,settled_cents,complete,settled,active_lease,final_balances,plan,reachable_states,authority,owner_review}`. requested_cents sums current payout amounts. Choose the reachable state by: complete first; then greatest received cents; then greatest number received; then shortest action sequence; then lexicographically smallest sequence. settled is its sorted received payout IDs; settled_cents sums them; active_lease is its bridge ID or null. final_balances maps every wallet ID to its cash in that state. plan is the chosen action-string sequence. reachable_states is the exact number of distinct reachable states, independent of the chosen plan.

authority is `{owners,payouts,leases}`: owners maps current owner ID to wallet ID; payouts and leases are sorted lists of the selected payloads including id but excluding revision/known/signed/void. Keep owner references in those payloads (do not replace their names with wallet names). Sort all dependency lists. This makes the evidence used for the search reviewable.

proposals is a list of up to four unique `{id,cost,owners,payouts,leases}`. Each of the last three is a list of replacement payloads in the same authority format (including id, excluding revision/known/signed/void). Replacements target existing IDs; different proposals never target the same stream/ID. A hypothetical subset applies whole replacements and sums costs. These are specific owner approvals which must be obtained; they cannot modify current evidence or be used by the current schedule. owner_review is null if none permits completion. Otherwise it is `{cost,proposals,plan}`, minimizing cost, then number of proposals, then sorted proposal IDs; plan is the canonical completing schedule under that subset. Include the empty zero-cost subset when current authority already permits completion.

Write the exact analysis of data/request.json to audit.json and run `python3 -m pytest`. If complete is true, submit complete. Otherwise leave no release.json, submit blocked, identify the actual timing/ownership/bridge obstacle, and provide claims.evidence with requested_cents, settled_cents, reachable_states, owner_proposals (the selected IDs or null). Additional explanation keys are allowed. A fixed artifact without a reusable engine is insufficient. Added diagnostic tests may intentionally demonstrate an obstacle; their failure alone does not invalidate a correct blocked submission.

Bounds: at most8 payouts,4 wallets,5 owners,4 bridge leases,40 delivered rows per stream,4 proposals, cents/balances at most1000. IDs contain ASCII letters, digits, hyphens. At most3^8 *5 execution states; no monetary unit enumeration or unbounded scheduling horizon is necessary. All proposed authority snapshots satisfy the same reference rules.
