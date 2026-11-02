# Replay worker (`payout_release/replay.py`)

`ReplayWorker(accounts, authority)` starts from the opening balances with nothing
dispatched, nothing received and no bridge active, and applies steps in order.
Each payout is dispatched at most once and received at most once.

* `dispatch:ID` – the payout is not yet dispatched and its source account holds at
  least its `cents`; the source is debited immediately. The destination is NOT
  credited yet.
* `receipt:ID` – the payout is dispatched and not yet received, and every payout in
  its `receipt_after` has been dispatched; the destination is credited. No cash is
  needed. These are conditions on the provider, not automatic follow-ups: a
  receipt is a separate step that happens only when scheduled.
* `draw:ID` – no bridge is active and every payout in its `activate_after` has been
  received; the bridge's cents are credited to its owner's account and it becomes
  the single active bridge.
* `repay:ID` – that bridge is active, its account holds its cents and every payout
  in `release_after` has been received; the account is debited and the bridge
  becomes inactive. A repaid bridge may be drawn again later.

Every step is atomic; there are no partial payouts, split bridges, overdrafts,
netting or cancellations. A rejected step raises `ReplayError` and the worker
state is unchanged. `replay(plan)` applies a whole plan and returns
`{settled, active_bridge, balances, complete}`; `complete` means every payout is
received and no bridge is active.
