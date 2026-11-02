python - <<'PY'
import json
from pathlib import Path
path = Path('data/operations.jsonl')
rows = [json.loads(line) for line in path.read_text().splitlines() if line]
rows = [r for r in rows if not (r['signed']['id'] == 'edge-cutover' and r['signed']['revision'] == 2)]
path.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
PY
