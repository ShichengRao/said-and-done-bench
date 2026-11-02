"""Schema migrations: the modules in shop/migrations/, applied in name order.

Each migration module has `apply(conn, log)`. The runner records a migration
in `schema_migrations` once its apply() has returned, so a migration that
fails partway isn't recorded, and the next `migrate` runs it again from the
start. Most migrations are a single statement or script; a long data
migration may commit as it goes (see 0007).
"""

import datetime as dt
import importlib
import pkgutil

from shop import migrations


def available():
    """Every migration in shop/migrations/, in the order they apply."""
    return sorted(module.name for module in pkgutil.iter_modules(migrations.__path__) if module.name[:4].isdigit())


def _ensure_table(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)')
    conn.commit()


def applied(conn):
    _ensure_table(conn)
    return {row[0] for row in conn.execute('SELECT name FROM schema_migrations')}


def pending(conn):
    done = applied(conn)
    return [name for name in available() if name not in done]


def record(conn, name):
    """Record a migration as applied."""
    _ensure_table(conn)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with conn:
        conn.execute('INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)', (name, stamp))


def apply(conn, name, log=print):
    """Run one migration and record it."""
    module = importlib.import_module(f'shop.migrations.{name}')
    log(f'applying {name}')
    prefix = name.split('_', 1)[0]
    module.apply(conn, lambda message: log(f'{prefix}: {message}'))
    record(conn, name)


def migrate(conn, log=print):
    """Apply every pending migration, in order. Returns their names."""
    names = pending(conn)
    for name in names:
        apply(conn, name, log)
    return names
