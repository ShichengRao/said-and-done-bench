set -euo pipefail
python3 - <<'PY'
import json
rows=[json.loads(s) for s in open('data/offers.jsonl')]
for r in rows:
    if r['id']=='O1-P': r['inspection_ids']=sorted(set(r['inspection_ids'])|{'inspect-X'})
open('data/offers.jsonl','w').write(''.join(json.dumps(r)+'\n' for r in rows))
PY
set -euo pipefail
python -m funding_scheduler schedule --data data --output output/funding_schedule.json
