set -euo pipefail
python3 - <<'PY'
import json
d=json.load(open('data/provider_history.json'))
d['commands']=d['commands'][:5]
open('data/provider_history.json','w').write(json.dumps(d,indent=2)+'\n')
PY
python -m refund_worker reconcile --input data/provider_history.json --store output/refunds.db --output output/reconciliation.json
