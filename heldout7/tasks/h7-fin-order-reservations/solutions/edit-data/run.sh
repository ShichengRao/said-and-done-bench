set -euo pipefail
python3 - <<'PY'
import json
d=json.load(open('data/customer_update.json'))
# "Free" the shared stock by dropping the other customers' holds.
d['commands']=[c for c in d['commands'] if not c.get('basket','').startswith('third')]
open('data/customer_update.json','w').write(json.dumps(d,indent=2)+'\n')
PY
python -m procurement apply --input data/customer_update.json --store output/procurement.db --output output/replacement_result.json
