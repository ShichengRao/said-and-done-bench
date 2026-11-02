import json
from pathlib import Path

class FileClient:
    def __init__(self, records_dir):
        self.root = Path(records_dir)

    def read_batch(self):
        def read(name):
            return json.loads((self.root / name).read_text())
        return {
            'period': read('period.json'),
            'deliveries': [json.loads(line) for line in (self.root / 'processor.jsonl').read_text().splitlines() if line.strip()],
            'journal': read('posted_journal.json'),
            'controls': read('signed_close_controls.json'),
            'bank': read('bank_settlement.json'),
        }
