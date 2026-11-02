Finish the procurement service so the customer can apply the attached order replacements together. Recompute the required ingredients, warehouse choices and fees using the current inventory and recipe rules.

Commit the replacement batch atomically, preserve unrelated reservations and retain the existing expiry and idempotent replay behavior.

Run the customer update through the service with the existing `apply` command to produce `output/replacement_result.json`, and add regression coverage for shared stock, rollback and retries. The README and `docs/` describe the records, planning rules and service contract.
