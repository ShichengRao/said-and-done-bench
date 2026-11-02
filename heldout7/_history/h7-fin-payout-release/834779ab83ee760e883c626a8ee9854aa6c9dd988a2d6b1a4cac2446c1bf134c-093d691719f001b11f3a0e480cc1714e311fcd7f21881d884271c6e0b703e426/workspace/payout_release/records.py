import json
from pathlib import Path

STREAMS = {'owner': 'owners', 'payout': 'payouts', 'bridge': 'bridges'}


def load_batch(data_dir):
    root = Path(data_dir)
    header = json.loads((root / 'batch.json').read_text())
    batch = {'batch': header['batch'], 'as_of': header['as_of'], 'accounts': header['accounts'],
             'owners': [], 'payouts': [], 'bridges': []}
    for line in (root / 'instructions.jsonl').read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            batch[STREAMS[row['stream']]].append({k: v for k, v in row.items() if k != 'stream'})
    return batch
