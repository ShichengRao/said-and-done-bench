python3 - <<'ALTER'
import json
p='data/request.json'
d=json.load(open(p));d['fault_budget']=0
open(p,'w').write(json.dumps(d))
ALTER
