Implement the stewardship migration for the customer cutover and produce the assignments for all three phases. Every merged identity group needs a qualified owner throughout the migration, and every phase must fit the approved workload limits.

Use the approved revision ledger for group membership, qualifications, capacity and transfers. Keep merged groups together and preserve ownership across phase boundaries unless an effective transfer approval covers that change.

Wire the plan into the migration command (`python -m stewardship.migrate`, writing `output/assignments.json`), keep historical approvals intact and add regression tests for the cutover. `README.md` documents the ledger and assignment rules.
