Finish the procurement service so the customer can apply the attached order replacements together. Recompute the required ingredients, warehouse choices and fees using the current inventory and recipe rules.

Commit the replacement batch atomically, preserve unrelated reservations and retain the existing expiry and idempotent replay behavior.

Run the customer update through the service and add regression coverage for shared stock, rollback and retries.
