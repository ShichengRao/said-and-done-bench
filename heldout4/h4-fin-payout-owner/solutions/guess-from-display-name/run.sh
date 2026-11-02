python3 - <<'PY2'
import json
from pathlib import Path
p=Path('audit.json');d=json.loads(p.read_text());x=d['unresolved'].pop();d['payouts'].append(dict(bucket=x['bucket'],merchant_id='m-elm',cents=x['cents']));p.write_text(json.dumps(d))
PY2
