"""The ledger: data/ledger.jsonl (or $LEDGERLY_DATA/ledger.jsonl), one transaction per line, oldest first."""

import json
import os
from pathlib import Path

from ledgerly.models import Transaction

DEFAULT_FOLDER = Path(__file__).resolve().parent.parent / 'data'


def folder():
    return Path(os.environ.get('LEDGERLY_DATA') or DEFAULT_FOLDER)


def path():
    return folder() / 'ledger.jsonl'


def load():
    if not path().exists():
        return []
    with open(path(), encoding='utf-8') as handle:
        return [Transaction.from_json(json.loads(line)) for line in handle if line.strip()]


def append(transactions):
    """Adds transactions at the end of the ledger, all of them or (if writing fails) none."""
    transactions = list(transactions)
    if not transactions:
        return
    text = ''.join(json.dumps(t.to_json(), ensure_ascii=False) + '\n' for t in transactions)
    path().parent.mkdir(parents=True, exist_ok=True)
    with open(path(), 'a', encoding='utf-8') as handle:
        handle.write(text)
