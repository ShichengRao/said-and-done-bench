python3 - <<'PY2'
import json
from pathlib import Path
p=Path('data/reservations.json');d=json.loads(p.read_text());p.write_text(json.dumps([r for r in d if r['facility']!='F1']))
PY2
