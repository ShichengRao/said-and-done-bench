"""Categories: data/rules.toml (or $LEDGERLY_DATA/rules.toml), a list of rules tried in order.

    [[rule]]
    match = "rewe"          # found anywhere in the description, ignoring case
    category = "groceries"

A description no rule matches is "uncategorized".
"""

import tomllib

from ledgerly import store


def load():
    path = store.folder() / 'rules.toml'
    if not path.exists():
        return []
    with open(path, 'rb') as handle:
        return [(rule['match'].lower(), rule['category']) for rule in tomllib.load(handle).get('rule', [])]


def categorize(description, rules=None):
    rules = load() if rules is None else rules
    lowered = description.lower()
    for needle, category in rules:
        if needle in lowered:
            return category
    return 'uncategorized'
