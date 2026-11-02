-- The accounts v2 users table (see docs/accounts-v2.md).
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    plan TEXT NOT NULL CHECK (plan IN ('starter', 'team', 'business')),
    created_at TEXT NOT NULL,
    marketing_opt_in INTEGER NOT NULL CHECK (marketing_opt_in IN (0, 1))
);
