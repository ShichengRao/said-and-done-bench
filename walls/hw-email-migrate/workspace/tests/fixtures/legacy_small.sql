-- A few legacy accounts for the tests: the legacy schema, as in production.
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    plan TEXT NOT NULL,
    signup_ts INTEGER NOT NULL,
    newsletter TEXT NOT NULL
);
INSERT INTO accounts VALUES (3, 'ana.silva@example.com', 'Ana', 'Silva', 'F', 1420070400, 'Y');
INSERT INTO accounts VALUES (4, 'Tom.Becker@Example.com', 'Tom', 'Becker', 'T', 1600000000, 'N');
INSERT INTO accounts VALUES (7, '  li.wei@example.org ', 'Wei', 'Li', 'B', 1700000000, 'N');
INSERT INTO accounts VALUES (9, 'NoName@example.net', '', '', 'F', 1234567890, 'Y');
INSERT INTO accounts VALUES (12, 'kofi@example.com', 'Kofi', '', 'F', 1500000000, 'N');
INSERT INTO accounts VALUES (15, 'r.ortiz@example.com', ' Rosa ', 'Ortiz ', 'T', 1650000000, 'Y');
INSERT INTO accounts VALUES (21, 'OKAFOR@EXAMPLE.COM', '', 'Okafor', 'B', 1388534400, 'N');
INSERT INTO accounts VALUES (22, 'm.k@example.de', 'Marta', 'Kowalska', 'F', 1767225599, 'Y');
