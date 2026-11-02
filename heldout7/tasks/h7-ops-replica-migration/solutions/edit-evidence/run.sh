python - <<'PY'
import json
from pathlib import Path
path = Path('data/fleet.json'); fleet = json.loads(path.read_text())
fleet['links'].append({'id': 'relay-03', 'revision': 1, 'source': 'n0', 'target': 'n3', 'enabled': True, 'valid_from': 0, 'valid_to': 20})
path.write_text(json.dumps(fleet, indent=2) + '\n')
PY
