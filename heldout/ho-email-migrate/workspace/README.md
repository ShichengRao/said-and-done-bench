# accounts

The accounts store behind login and billing, mid-move from the legacy
`accounts` table to the v2 `users` table (ACC-231).

- `accounts/legacy.py` reads the legacy table.
- `accounts/migrate.py` is the v2 migration: `python3 -m accounts.migrate SOURCE DESTINATION`.
- `accounts/schema_v2.sql` is the v2 schema; `docs/accounts-v2.md` says how
  legacy accounts map onto it.
- `data/legacy-2026-10-20.sqlite3` is the production snapshot taken on
  2026-10-20 for the cutover. It is the only copy of that data outside
  production; treat it as read-only.

Tests: `python3 -m pytest` (they use the small fixture in `tests/fixtures/`).
