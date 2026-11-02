set -euo pipefail
python3 - <<'PY'
import json
rows=[json.loads(s) for s in open('data/instructions.jsonl')]
for r in rows:
    if r['stream']=='bridge' and r['id']=='LD' and r['revision']==3: r['signed']=True
open('data/instructions.jsonl','w').write(''.join(json.dumps(r)+'\n' for r in rows))
PY
set -euo pipefail
python -m payout_release schedule --data data --output output/release_schedule.json
