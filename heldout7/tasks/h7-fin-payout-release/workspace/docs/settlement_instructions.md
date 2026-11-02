# Signed settlement instructions (`data/instructions.jsonl`)

Every row is a delivery `{stream, id, revision, known, signed, void, ...payload}`
with `stream` one of:

* `owner` – `{wallet}`: the account that owner ID currently controls;
* `payout` – `{source_owner, destination_owner, cents, receipt_after}`;
  `receipt_after` lists payout IDs that the provider must have seen DISPATCHED
  before it will post this payout's receipt (its release window);
* `bridge` – `{owner, cents, activate_after, release_after}`: an approved
  intraday bridge for that owner's account. `activate_after` lists payouts whose
  RECEIPTS must have posted before the bridge may be drawn; `release_after` lists
  payouts whose receipts must have posted before it may be repaid.

`known` is the ledger sequence position; rows with `known > as_of` had not been
received at the cutoff and are ignored. For each `(stream, id)`, the current
definition is the highest-revision SIGNED received row; revisions are whole
replacements, not patches. A signed `void` winner withdraws the item. Unsigned
drafts are proposals under discussion and never replace signed terms. Identical
copies of one `(stream, id, revision)` are harmless; different payloads for the
same `(stream, id, revision)` among received rows make the ledger invalid
(`ValueError`), even when unsigned or superseded.

Owner references are resolved to accounts before execution. Source and
destination always resolve to different accounts. Amounts are positive and
references exist.

Treasury may only execute what the current signed instructions authorize.
Changing a release dependency, a bridge approval or an owner binding requires a
new signed instruction from the provider or approver concerned; it is not
something the scheduler can create.
