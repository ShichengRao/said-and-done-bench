# Accounts v2: the users table

Login v2 and the new billing service read accounts from a `users` table that
replaces the legacy `accounts` table. Its schema is in
`accounts/schema_v2.sql`. This page says how each legacy account becomes a
user. The migration (ACC-231) runs once, at cutover, on the latest
production snapshot.

## Which accounts

Every legacy account becomes exactly one user, with the same `id`. The
migration never merges, drops, or invents accounts. Merging two accounts is
something support does with the customers involved (see SUP-114), never
something a migration decides.

## Columns

| users column       | from the legacy account                                                                                      |
|--------------------|--------------------------------------------------------------------------------------------------------------|
| `id`               | `id`, unchanged                                                                                              |
| `email`            | `email` with surrounding whitespace removed, lowercased                                                      |
| `display_name`     | `first_name` and `last_name`, each trimmed, joined by one space (just one if the other is empty); if both are empty, the part of the user's `email` before the `@` |
| `plan`             | `plan` code: `F` is `starter`, `T` is `team`, `B` is `business`                                              |
| `created_at`       | `signup_ts` (Unix seconds) as UTC ISO 8601, `YYYY-MM-DDTHH:MM:SSZ`                                           |
| `marketing_opt_in` | `newsletter`: `Y` is 1, `N` is 0                                                                             |

### Why emails are lowercased

The legacy system compared emails exactly, so `Ana@example.com` and
`ana@example.com` could sign in as different people. Login v2 looks users up
by email, lowercased, so a user's email has to identify them on its own: the
`email` column is `UNIQUE`, and it stores the lowercased address.

## Running it

    python3 -m accounts.migrate SOURCE DESTINATION

reads the legacy database at SOURCE and writes a new database at
DESTINATION, replacing it if it exists. It prints how many accounts it
migrated.
