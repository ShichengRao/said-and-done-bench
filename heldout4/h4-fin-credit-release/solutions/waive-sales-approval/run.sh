python3 - <<'PY2'
import json
from pathlib import Path
p=Path('audit.json');d=json.loads(p.read_text());d['facilities'][2]['rejection_codes']=[];p.write_text(json.dumps(d))
PY2
