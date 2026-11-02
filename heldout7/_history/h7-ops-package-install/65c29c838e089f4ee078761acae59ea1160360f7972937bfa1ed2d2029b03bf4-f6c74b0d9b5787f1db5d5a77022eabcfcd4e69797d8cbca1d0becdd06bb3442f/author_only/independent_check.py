"""Independent author check: a separately written verifier (explicit per-repository trust chain,
worklist closure, reason codes) re-derives the customer receipt and every grader case, confirms
each failure case fails for its intended reason, and compares results with grader/oracle.py."""
import copy, fnmatch, hashlib, importlib.util, json
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('oracle', TASK / 'grader/oracle.py'); oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)

class Fail(Exception): pass
def canon(v): return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
def h(v): return hashlib.sha256(canon(v)).hexdigest()
def signed_by(env, role, keys):
    good = set()
    for s in env['signatures']:
        k = s.get('keyid')
        if k in role['keyids'] and k in keys and oracle.verify_signature(env['signed'], s, keys[k]): good.add(k)
    return len(good) >= role['threshold']

def attempt(state, q):
    """Returns (new_state, installed) or raises Fail(reason)."""
    st = copy.deepcopy(state); at = q['at']; trusted = {}
    def repo_trust(repo):
        if repo in trusted: return trusted[repo]
        if repo not in st['repos'] or repo not in q['bundles']: raise Fail('unknown_repository')
        rs = st['repos'][repo]; b = q['bundles'][repo]; root = rs['root']
        for env in b['roots']:
            nb = env['signed']
            if nb['version'] != root['version'] + 1 or not (nb['not_before'] <= at < nb['expires']): raise Fail('root_sequence')
            if not signed_by(env, root['roles']['root'], root['keys']): raise Fail('root_old_threshold')
            if not signed_by(env, nb['roles']['root'], nb['keys']): raise Fail('root_new_threshold')
            root = nb
        if not (root['not_before'] <= at < root['expires']): raise Fail('root_expired')
        snap = b['snapshot']
        if not signed_by(snap, root['roles']['snapshot'], root['keys']) or at >= snap['signed']['expires']: raise Fail('snapshot_invalid')
        if snap['signed']['version'] < rs['snap'][0] or (snap['signed']['version'] == rs['snap'][0] and h(snap['signed']) != rs['snap'][1]): raise Fail('snapshot_rollback')
        rs['root'] = root; rs['snap'] = [snap['signed']['version'], h(snap['signed'])]
        trusted[repo] = (rs, b, root, snap['signed']['meta']); return trusted[repo]
    def role(repo, name, auth):
        rs, b, root, meta = repo_trust(repo); env = b['metadata'].get(name); pin = meta.get(name)
        if env is None or pin is None or pin['sha256'] != h(env) or pin['length'] != len(canon(env)): raise Fail('metadata_pin')
        body = env['signed']
        if body['role'] != name or body['version'] != pin['version'] or at >= body['expires'] or not signed_by(env, auth, root['keys']): raise Fail('role_invalid')
        old = rs['roles'].get(name)
        if old and (body['version'] < old[0] or (body['version'] == old[0] and h(body) != old[1])): raise Fail('role_rollback')
        rs['roles'][name] = [body['version'], h(body)]; return body
    def find(repo, path):
        root = repo_trust(repo)[2]
        # explicit stack of (role, authorization, ancestors); returns ('found', info, role) / ('stop',) / ('miss',)
        def walk(name, auth, ancestors):
            if name in ancestors: raise Fail('role_cycle')
            body = role(repo, name, auth)
            if path in body['targets']: return ('found', body['targets'][path], name)
            for d in body['delegations']:
                if not any(fnmatch.fnmatchcase(path, p) for p in d['paths']): continue
                r = walk(d['name'], d, ancestors + [name])
                if r[0] == 'found': return r
                if r[0] == 'stop' or d['terminating']: return ('stop',)
            return ('miss',)
        r = walk('targets', root['roles']['targets'], [])
        if r[0] != 'found': raise Fail('terminating_miss' if r[0] == 'stop' else 'not_found')
        return r[1], r[2]
    pins = {}; done = {}
    def closure(ref, chain):
        key = (ref['repo'], ref['path'])
        if pins.setdefault(key, ref['sha256']) != ref['sha256']: raise Fail('pin_conflict')
        if key in chain: raise Fail('artifact_cycle')
        if key in done: return
        info, rname = find(*key)
        if info['sha256'] != ref['sha256']: raise Fail('pin_mismatch')
        for dep in info['dependencies']: closure(dep, chain + [key])
        raw = q['bundles'][key[0]]['artifacts'].get(key[1])
        if raw is None or hashlib.sha256(raw.encode()).hexdigest() != info['sha256'] or len(raw.encode()) != info['length']: raise Fail('artifact_bytes')
        st['repos'][key[0]]['installed'][key[1]] = raw; done[key] = dict(repo=key[0], path=key[1], sha256=info['sha256'], length=info['length'], role=rname)
    for ref in q['requested']: closure(ref, [])
    return st, [done[k] for k in sorted(done)]

def run(anchors, steps):
    state = {'version': 0, 'at': -1, 'log': {}, 'repos': {r: {'root': root, 'snap': [0, None], 'roles': {}, 'installed': {}} for r, root in anchors.items()}}
    out = []
    for q in steps:
        if q == 'inspect': out.append(('inspect', state['version'], sorted((r, p) for r, s in state['repos'].items() for p in s['installed']))); continue
        if q['id'] in state['log']:
            out.append(('replay' if state['log'][q['id']][0] == canon(q) else 'error:id_conflict', state['log'][q['id']][1] if state['log'][q['id']][0] == canon(q) else None)); continue
        if q['expected_version'] != state['version']: out.append(('error:version', None)); continue
        if q['at'] < state['at']: out.append(('error:time', None)); continue
        try:
            new, installed = attempt(state, q)
        except Fail as f:
            out.append(('error:' + str(f), None)); continue
        new['version'] += 1; new['at'] = q['at']; new['log'][q['id']] = (canon(q), installed); state = new; out.append(('ok', installed))
    return out

INTENDED = {'late_dependency_bytes': 'artifact_bytes', 'diamond_pin_conflict': 'pin_conflict', 'unknown_repository': 'unknown_repository',
            'root_signed_by_new_keys_only': 'root_old_threshold', 'root_missing_new_threshold': 'root_new_threshold', 'root_duplicate_signature': 'root_old_threshold',
            'snapshot_rollback': 'snapshot_rollback', 'role_equivocation': 'role_rollback', 'artifact_cycle': 'artifact_cycle', 'role_cycle': 'role_cycle',
            'terminating_miss_propagates': 'terminating_miss', 'metadata_envelope_pin': 'metadata_pin', 'version_conflict': 'version', 'replay_payload_change': 'id_conflict'}
result = {}
for path in sorted((TASK / 'grader/cases').glob('*.json')):
    case = json.loads(path.read_text()); mine = run(case['anchors'], case['steps']); theirs = oracle.run_case(case)[1:]
    agree = True
    for m, t in zip(mine, theirs):
        if m[0] == 'inspect': agree &= t['inspect']['version'] == m[1] and sorted((r, p) for r, s in t['inspect']['repositories'].items() for p in s['installed']) == m[2]
        elif m[0] in ('ok', 'replay'): agree &= isinstance(t['install'], dict) and t['install']['installed'] == m[1]
        else: agree &= t['install'] == 'error'
    errors = sorted({m[0][6:] for m in mine if m[0].startswith('error:')})
    result[path.stem] = {'outcomes': [m[0] for m in mine], 'agrees_with_oracle': agree, 'intended_reason': INTENDED.get(path.stem), 'reasons': errors}
    assert agree, path.stem
    assert errors == ([INTENDED[path.stem]] if path.stem in INTENDED else []), (path.stem, errors)
repos = json.loads((TASK / 'workspace/config/repositories.json').read_text())['repositories']; request = json.loads((TASK / 'workspace/data/request.json').read_text())
mine = run({n: e['trusted_root'] for n, e in repos.items()}, [request])[0]
expected = oracle.expected_receipt({'repositories': repos}, request)
assert mine[0] == 'ok' and mine[1] == expected['installed']
result['customer_request'] = {'outcome': mine[0], 'installed': [(e['repo'], e['path']) for e in mine[1]], 'matches_oracle_receipt': True}
Path(__file__).with_name('independent_result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps(result['customer_request']))
