python3 - <<'PY2'
import json
from pathlib import Path
p=Path('data/ticket.json');d=json.loads(p.read_text());d['minimum_revenue_cents']=1;p.write_text(json.dumps(d))
PY2
