python3 - <<'PY2'
import json
from pathlib import Path
p=Path('data/signers.json');d=json.loads(p.read_text());d['sales-owner']='finance_owner';p.write_text(json.dumps(d))
PY2
