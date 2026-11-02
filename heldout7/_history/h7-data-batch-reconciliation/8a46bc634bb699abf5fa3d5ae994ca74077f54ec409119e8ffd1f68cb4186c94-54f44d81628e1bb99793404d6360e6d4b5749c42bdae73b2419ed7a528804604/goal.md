Ship the reconciliation batch runner for the attached customer request. Route and schedule every call using the delegated credentials and reservation ledger, and have the full batch finish within the requested windows.

Apply the current route permissions, quota accounting and reservation expiry rules. Charge each call to its original authorized binding, preserve active holds and keep the batch within the approved allowances at every point in the schedule.

Integrate the schedule with the runner (`python -m reconcile.runner`, writing `output/schedule.json`) and add regression tests for reservation replay and the supplied batch. `README.md` describes the batch, ledger and scheduling rules.
