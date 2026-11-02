"""Trusted in-memory installer oracle (algorithm from the h6-ops-provenance honest gate).
Never imports candidate code. A failing install leaves the state untouched."""
import copy, fnmatch, hashlib, json


def canonical(v): return json.dumps(v, sort_keys=True, separators=(',', ':')).encode()
def digest(x): return hashlib.sha256(canonical(x)).hexdigest()


def verify_signature(body, signature, key):
    try:
        n = int(key['n'], 16); e = key['e']; size = (n.bit_length() + 7) // 8; raw = bytes.fromhex(signature['sig'])
        if len(raw) != size or int.from_bytes(raw, 'big') >= n: return False
        tail = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(canonical(body)).digest()
        pad = size - len(tail) - 3
        if pad < 8: return False
        return pow(int.from_bytes(raw, 'big'), e, n).to_bytes(size, 'big') == b'\x00\x01' + b'\xff' * pad + b'\x00' + tail
    except (ValueError, KeyError, TypeError, OverflowError):
        return False


def threshold(e, role, keys):
    votes = {s.get('keyid') for s in e['signatures'] if s.get('keyid') in role['keyids'] and s.get('keyid') in keys and verify_signature(e['signed'], s, keys[s['keyid']])}
    if len(votes) < role['threshold']: raise ValueError('signature threshold')


class Store:
    def __init__(self, anchors):
        self.s = dict(anchors=copy.deepcopy(anchors), version=0, at=-1, requests={},
                      repos={n: dict(root=copy.deepcopy(r), snapshot_version=0, snapshot_digest=None, roles={}, installed={}) for n, r in anchors.items()})

    def inspect(self, s=None):
        s = s or self.s
        return dict(version=s['version'], at=s['at'], repositories={name: dict(root_version=r['root']['version'], snapshot_version=r['snapshot_version'],
                    roles={k: v['version'] for k, v in r['roles'].items()},
                    installed={p: dict(length=len(raw.encode()), sha256=hashlib.sha256(raw.encode()).hexdigest()) for p, raw in r['installed'].items()})
                    for name, r in s['repos'].items()})

    def install(self, request):
        s = copy.deepcopy(self.s); q = copy.deepcopy(request); rid = q['id']; payload = canonical(q).decode()
        if rid in s['requests']:
            if s['requests'][rid]['payload'] != payload: raise ValueError('request ID conflict')
            return copy.deepcopy(s['requests'][rid]['response'])
        if q['expected_version'] != s['version']: raise ValueError('version conflict')
        at = q['at']
        if at < s['at']: raise ValueError('time rollback')
        prepared = {}; pins = {}; resolved = {}; visiting = set()

        def prepare(repo):
            if repo in prepared: return prepared[repo]
            if repo not in s['repos'] or repo not in q['bundles']: raise ValueError('unknown repository')
            state = s['repos'][repo]; b = q['bundles'][repo]; root = state['root']
            for e in b['roots']:
                new = e['signed']
                if new['type'] != 'root' or new['version'] != root['version'] + 1 or not new['not_before'] <= at < new['expires']: raise ValueError('root sequence')
                threshold(e, root['roles']['root'], root['keys']); threshold(e, new['roles']['root'], new['keys']); root = copy.deepcopy(new)
            if not root['not_before'] <= at < root['expires']: raise ValueError('expired root')
            state['root'] = root; snap = b['snapshot']; body = snap['signed']; threshold(snap, root['roles']['snapshot'], root['keys'])
            if body['type'] != 'snapshot' or at >= body['expires']: raise ValueError('snapshot')
            h = digest(body)
            if body['version'] < state['snapshot_version'] or (body['version'] == state['snapshot_version'] and h != state['snapshot_digest']): raise ValueError('snapshot rollback')
            state['snapshot_version'] = body['version']; state['snapshot_digest'] = h
            prepared[repo] = (state, b, root, body); return prepared[repo]

        def lookup(repo, path):
            state, b, root, snapshot = prepare(repo)
            def visit(name, authorization, stack):
                if name in stack: raise ValueError('delegation cycle')
                e = b['metadata'].get(name); pin = snapshot['meta'].get(name)
                if e is None or pin is None or len(canonical(e)) != pin['length'] or digest(e) != pin['sha256']: raise ValueError('metadata pin')
                body = e['signed']
                if body['type'] != 'targets' or body['role'] != name or body['version'] != pin['version'] or at >= body['expires']: raise ValueError('role identity')
                threshold(e, authorization, root['keys']); old = state['roles'].get(name); h = digest(body)
                if old and (body['version'] < old['version'] or (body['version'] == old['version'] and h != old['digest'])): raise ValueError('role rollback')
                state['roles'][name] = {'version': body['version'], 'digest': h}
                if path in body['targets']: return (body['targets'][path], name), False
                for d in body['delegations']:
                    if any(fnmatch.fnmatchcase(path, p) for p in d['paths']):
                        found, terminated = visit(d['name'], d, stack | {name})
                        if found: return found, False
                        if terminated or d['terminating']: return None, True
                return None, False
            found, _ = visit('targets', root['roles']['targets'], set())
            if found is None: raise ValueError('unresolved target')
            return found

        def resolve(ref):
            key = (ref['repo'], ref['path']); pin = ref['sha256']
            if key in pins and pins[key] != pin: raise ValueError('pin conflict')
            pins[key] = pin
            if key in visiting: raise ValueError('dependency cycle')
            if key in resolved: return
            visiting.add(key); info, role = lookup(*key)
            if info['sha256'] != pin: raise ValueError('pin mismatch')
            for dep in info['dependencies']: resolve(dep)
            state, b, _, _ = prepared[key[0]]; raw = b['artifacts'].get(key[1])
            if raw is None or len(raw.encode()) != info['length'] or hashlib.sha256(raw.encode()).hexdigest() != pin: raise ValueError('artifact integrity')
            state['installed'][key[1]] = raw; resolved[key] = dict(repo=key[0], path=key[1], sha256=pin, length=info['length'], role=role); visiting.remove(key)

        for ref in q['requested']: resolve(ref)
        s['version'] += 1; s['at'] = at; response = {**self.inspect(s), 'installed': [resolved[k] for k in sorted(resolved)]}
        s['requests'][rid] = {'payload': payload, 'response': copy.deepcopy(response)}; self.s = s
        return response


def run_case(case):
    """Expected outcome list: initialize summary, then per step a response, 'error' or an inspect summary."""
    store = Store(case['anchors']); outcomes = [{'initialize': store.inspect()}]
    for step in case['steps']:
        if step == 'inspect': outcomes.append({'inspect': store.inspect()}); continue
        try: outcomes.append({'install': store.install(step)})
        except ValueError: outcomes.append({'install': 'error'})
    return outcomes


def expected_receipt(repositories, request):
    store = Store({name: entry['trusted_root'] for name, entry in repositories['repositories'].items()})
    return {'request_id': request['id'], **store.install(request)}
