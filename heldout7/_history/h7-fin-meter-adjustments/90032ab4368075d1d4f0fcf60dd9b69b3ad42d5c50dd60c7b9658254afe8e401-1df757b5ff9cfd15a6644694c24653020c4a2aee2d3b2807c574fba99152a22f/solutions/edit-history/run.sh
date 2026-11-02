set -euo pipefail
python3 - <<'PY'
import json
h=json.load(open('data/customer_history.json'))
h['commands']=[c for c in h['commands'] if c['operation_id']!='right-retracted']
open('data/customer_history.json','w').write(json.dumps(h,indent=2)+'\n')
PY
python -m meter_billing replay --history data/customer_history.json --store output/billing.db --output output/adjustments.json
