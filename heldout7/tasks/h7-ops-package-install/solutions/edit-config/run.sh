python - <<'PY'
import json
config = json.load(open('config/repositories.json')); request = json.load(open('data/request.json'))
for name, bundle in request['bundles'].items():
    config['repositories'][name]['trusted_root'] = bundle['roots'][0]['signed']; bundle['roots'] = []
json.dump(config, open('config/repositories.json', 'w'), indent=1); json.dump(request, open('data/request.json', 'w'), indent=1)
PY
set +e
python -m installer install --repositories config/repositories.json --request data/request.json --store state/installer.db --receipt output/install_receipt.json
status=$?
set -e
test "$status" -eq 2
