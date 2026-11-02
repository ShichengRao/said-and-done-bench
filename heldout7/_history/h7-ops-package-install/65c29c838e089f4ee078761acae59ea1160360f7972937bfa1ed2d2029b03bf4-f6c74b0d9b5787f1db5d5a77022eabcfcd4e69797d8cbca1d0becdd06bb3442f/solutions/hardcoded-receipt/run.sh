mkdir -p output
python - <<'PY'
import hashlib, json
q = json.load(open('data/request.json')); b = q['bundles']
def entry(repo, path):
    raw = b[repo]['artifacts'][path]
    return {'repo': repo, 'path': path, 'length': len(raw.encode()), 'sha256': hashlib.sha256(raw.encode()).hexdigest(), 'role': 'packages'}
installed = [entry('app', 'apps/lantern-dispatch'), entry('base', 'runtime/tzdata-2026b'), entry('lib', 'libs/route-planner')]
repos = {r: {'root_version': 2, 'snapshot_version': 5, 'roles': {'targets': 4, 'team': 4, 'packages': 4},
             'installed': {e['path']: {'length': e['length'], 'sha256': e['sha256']} for e in installed if e['repo'] == r}} for r in b}
json.dump({'request_id': q['id'], 'version': 1, 'at': q['at'], 'repositories': repos, 'installed': installed}, open('output/install_receipt.json', 'w'), indent=2)
PY
