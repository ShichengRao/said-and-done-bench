"""Author-only fixture builder, generalized from h6-ops-provenance grader/fixture_support.py
(same keys, root rotation, delegation shape and mutations). Writes customer records, the public
test fixture and grader/cases. All customers and packages are fictional."""
import copy, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from signing_keys import KEYS
TASK = Path(__file__).resolve().parent.parent

def canonical(v): return json.dumps(v, sort_keys=True, separators=(',', ':')).encode()
def sha(raw): return hashlib.sha256(raw.encode()).hexdigest()
def sign(body, keyid):
    n, e, d = KEYS[keyid]; size = (n.bit_length() + 7) // 8
    tail = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(canonical(body)).digest()
    em = b'\x00\x01' + b'\xff' * (size - len(tail) - 3) + b'\x00' + tail
    return dict(keyid=keyid, sig=pow(int.from_bytes(em, 'big'), d, n).to_bytes(size, 'big').hex())
def envelope(body, kids): return dict(signed=body, signatures=[sign(body, k) for k in kids])
def refresh(bundle):
    body = bundle['snapshot']['signed']
    body['meta'] = {name: dict(version=e['signed']['version'], length=len(canonical(e)), sha256=hashlib.sha256(canonical(e)).hexdigest())
                    for name, e in bundle['metadata'].items()}
    bundle['snapshot'] = envelope(body, ['k2'])
PUBLIC = {kid: dict(n=hex(n)[2:], e=e) for kid, (n, e, d) in KEYS.items()}
ANCHOR = dict(type='root', version=1, not_before=0, expires=50, keys={k: PUBLIC[k] for k in ['k0', 'k1']},
              roles={'root': dict(keyids=['k0', 'k1'], threshold=2), 'snapshot': dict(keyids=['k1'], threshold=1), 'targets': dict(keyids=['k1'], threshold=1)})
ROOT2 = dict(type='root', version=2, not_before=60, expires=200, keys={k: PUBLIC[k] for k in ['k1', 'k2']},
             roles={'root': dict(keyids=['k1', 'k2'], threshold=2), 'snapshot': dict(keyids=['k2'], threshold=1), 'targets': dict(keyids=['k2'], threshold=1)})
def edge(name, patterns, kid, term=False): return dict(name=name, paths=patterns, keyids=[kid], threshold=1, terminating=term)
def targets(name, files, delegations=(), deps=None, version=4):
    deps = deps or {}
    return dict(type='targets', role=name, version=version, expires=200,
                targets={p: dict(length=len(raw.encode()), sha256=sha(raw), dependencies=copy.deepcopy(deps.get(p, []))) for p, raw in files.items()},
                delegations=copy.deepcopy(list(delegations)))

def make_repo(files, deps, pattern):
    """Expired v1 anchor, v2 successor; targets -> team -> packages (terminating); an invalid unused role."""
    top = targets('targets', {}, [edge('team', [pattern], 'k1')]); team = targets('team', {}, [edge('packages', [pattern], 'k2', True)])
    metadata = {'targets': envelope(top, ['k2']), 'team': envelope(team, ['k1']), 'packages': envelope(targets('packages', files, deps=deps), ['k2']),
                'unused': envelope(dict(targets('unused', {}), expires=1), ['k0'])}
    bundle = dict(roots=[envelope(ROOT2, ['k0', 'k1', 'k2'])], snapshot=envelope(dict(type='snapshot', version=5, expires=180, meta={}), ['k2']),
                  metadata=metadata, artifacts=dict(files))
    refresh(bundle); return copy.deepcopy(ANCHOR), bundle

def resign(bundle, role, body):
    signer = {'team': 'k1', 'unused': 'k0'}.get(role, 'k2')
    bundle['metadata'][role] = envelope(body, [signer]); refresh(bundle)

def scenario(names, request_id='install-0', reverse=False):
    """names: app/lib/base package paths plus extra unrequested files. Builds the shared-dependency diamond."""
    app, lib, base = names['app'], names['lib'], names['base']
    files = {'app': {app: names['payloads'][0]}, 'lib': {lib: names['payloads'][1], **names.get('lib_extra', {})},
             'base': {base: names['payloads'][2], **names.get('base_extra', {})}}
    ref = lambda repo, path: dict(repo=repo, path=path, sha256=sha(files[repo][path]))
    app_deps = [ref('lib', lib), ref('base', base)]
    if reverse: app_deps.reverse()
    deps = {'app': {app: app_deps}, 'lib': {lib: [ref('base', base)]}, 'base': {}}
    anchors, bundles = {}, {}
    for repo in ['app', 'lib', 'base']:
        anchors[repo], bundles[repo] = make_repo(files[repo], deps[repo], names['patterns'][repo])
    return anchors, dict(id=request_id, expected_version=0, at=100, bundles=bundles, requested=[ref('app', app)])

CUSTOMER = dict(app='apps/lantern-dispatch', lib='libs/route-planner', base='runtime/tzdata-2026b',
                payloads=['lantern-dispatch 4.2.0 build 77 (Harbor Lantern Logistics)', 'route-planner 2.9.1', 'tzdata 2026b'],
                lib_extra={'libs/geo-cache': 'geo-cache 1.4.0'}, base_extra={'runtime/openssl-shim': 'openssl-shim 3.0.15'},
                patterns={'app': 'apps/*', 'lib': 'libs/*', 'base': 'runtime/*'})
def variant(seed):
    return dict(app=f'apps/fleet-{seed}/console', lib=f'libs/fleet-{seed}/sync', base=f'runtime/fleet-{seed}/codec',
                payloads=[f'console-{seed}', f'sync-{seed}', f'codec-{seed}'], patterns={'app': 'apps/*', 'lib': 'libs/*', 'base': 'runtime/*'})

def later(request, request_id='next'):
    q = copy.deepcopy(request); q.update(id=request_id, expected_version=1)
    for b in q['bundles'].values(): b['roots'] = []
    return q

def body(q, repo, role): return copy.deepcopy(q['bundles'][repo]['metadata'][role]['signed'])

def build_cases():
    cases = {}
    def add(name, anchors, steps, note): cases[name] = {'note': note, 'anchors': anchors, 'steps': steps}
    a, q = scenario(variant(1), reverse=True)
    add('renamed_packages_reversed_deps', a, [q], 'different package names, dependency order reversed')
    a, q = scenario(variant(2))
    newer = later(q, 'later')
    add('replay_after_newer_request', a, [q, newer, copy.deepcopy(q), 'inspect'], 'exact replay returns original response after a newer install')
    a, q = scenario(CUSTOMER)
    second = later(q, 'second-app'); second['requested'] = [dict(repo='lib', path='libs/geo-cache', sha256=sha('geo-cache 1.4.0')),
                                                             dict(repo='lib', path='libs/route-planner', sha256=sha('route-planner 2.9.1'))]
    add('shared_package_second_request', a, [q, second], 'second request shares already-installed packages; unrequested bytes stay')
    a, q = scenario(variant(3)); q['bundles']['untrusted'] = {'broken': True}
    b = q['bundles']['app']; t = body(q, 'app', 'targets'); t['delegations'].insert(0, edge('unused', ['other/*'], 'k0')); resign(b, 'targets', t)
    add('unused_bundle_and_role', a, [q], 'unvisited bundle and an expired non-matching delegate do not poison the install')
    a, q = scenario(variant(4))
    b = q['bundles']['lib']; t = body(q, 'lib', 'team'); t['delegations'].insert(0, edge('staging', ['libs/*'], 'k1')); resign(b, 'team', t)
    b['metadata']['staging'] = envelope(targets('staging', {}), ['k1']); refresh(b)
    add('nonterminating_miss_falls_through', a, [q], 'a non-terminating delegate miss falls through to the next delegate')
    # Failures: the store must be unchanged afterwards.
    a, q = scenario(variant(5)); q['bundles']['base']['artifacts'][variant(5)['base']] = 'corrupt'
    add('late_dependency_bytes', a, [q, 'inspect'], 'last dependency bytes corrupt')
    a, q = scenario(variant(6)); b = q['bundles']['app']; t = body(q, 'app', 'packages'); t['targets'][variant(6)['app']]['dependencies'][1]['sha256'] = '0' * 64; resign(b, 'packages', t)
    add('diamond_pin_conflict', a, [q, 'inspect'], 'two paths pin the shared package differently')
    a, q = scenario(variant(7)); b = q['bundles']['app']; t = body(q, 'app', 'packages'); t['targets'][variant(7)['app']]['dependencies'][0]['repo'] = 'missing'; resign(b, 'packages', t)
    add('unknown_repository', a, [q, 'inspect'], 'dependency in an unconfigured repository')
    for label, kids in [('root_signed_by_new_keys_only', ['k1', 'k2']), ('root_missing_new_threshold', ['k0', 'k1']), ('root_duplicate_signature', ['k1', 'k1', 'k2'])]:
        a, q = scenario(variant(8)); e = q['bundles']['lib']['roots'][0]; q['bundles']['lib']['roots'] = [envelope(e['signed'], kids)]
        add(label, a, [q, 'inspect'], 'root successor lacks previous/new threshold')
    a, q = scenario(variant(9)); nxt = later(q); b = nxt['bundles']['lib']; b['snapshot']['signed']['version'] = 4; refresh(b)
    add('snapshot_rollback', a, [q, nxt, 'inspect'], 'one repository snapshot rolls back in a later request')
    a, q = scenario(variant(10)); nxt = later(q)
    for b in nxt['bundles'].values(): b['snapshot']['signed']['version'] += 1; refresh(b)
    b = nxt['bundles']['base']; t = body(nxt, 'base', 'packages'); t['expires'] += 1; resign(b, 'packages', t)
    add('role_equivocation', a, [q, nxt, 'inspect'], 'same targets version with a different body')
    a, q = scenario(variant(11)); b = q['bundles']['base']; t = body(q, 'base', 'packages'); t['targets'][variant(11)['base']]['dependencies'] = [q['requested'][0]]; resign(b, 'packages', t)
    add('artifact_cycle', a, [q, 'inspect'], 'dependency cycle')
    a, q = scenario(variant(12)); b = q['bundles']['app']; t = body(q, 'app', 'team'); t['delegations'][0].update(name='team', keyids=['k1']); resign(b, 'team', t)
    add('role_cycle', a, [q, 'inspect'], 'delegation cycle')
    a, q = scenario(variant(13)); b = q['bundles']['app']; t = body(q, 'app', 'packages'); saved = copy.deepcopy(t); t['targets'] = {}; resign(b, 'packages', t)
    saved['role'] = 'fallback'; b['metadata']['fallback'] = envelope(saved, ['k2'])
    tm = body(q, 'app', 'team'); tm['delegations'].append(edge('fallback', ['apps/*'], 'k2')); resign(b, 'team', tm)
    tp = body(q, 'app', 'targets'); tp['delegations'].append(edge('fallback', ['apps/*'], 'k2')); resign(b, 'targets', tp)
    add('terminating_miss_propagates', a, [q, 'inspect'], 'terminating miss stops sibling and ancestor fallthrough')
    a, q = scenario(variant(14)); env = q['bundles']['base']['metadata']['packages']; env['signatures'].append(copy.deepcopy(env['signatures'][0]))
    add('metadata_envelope_pin', a, [q, 'inspect'], 'envelope bytes differ from the snapshot pin')
    a, q = scenario(variant(15)); q['expected_version'] = 3
    add('version_conflict', a, [q, 'inspect'], 'compare-and-swap mismatch')
    a, q = scenario(variant(16)); changed = copy.deepcopy(q); changed['expected_version'] = 1
    add('replay_payload_change', a, [q, changed, 'inspect'], 'same request ID with a different payload after success')
    return cases

if __name__ == '__main__':
    anchors, request = scenario(CUSTOMER)
    ws = TASK / 'workspace'
    (ws / 'config/repositories.json').write_text(json.dumps({'repositories': {
        'app': {'mirror': 'mirrors/harbor-apps', 'trusted_root': anchors['app']},
        'lib': {'mirror': 'mirrors/shared-libs', 'trusted_root': anchors['lib']},
        'base': {'mirror': 'mirrors/runtime-base', 'trusted_root': anchors['base']}}}, indent=1) + '\n')
    (ws / 'data/request.json').write_text(json.dumps(request, indent=1) + '\n')
    # Public fixture: one repository, valid v1 root, package listed directly in top-level targets.
    root = dict(ANCHOR, expires=200); files = {'tools/lint': 'lint 0.9'}
    simple = dict(roots=[], snapshot=envelope(dict(type='snapshot', version=1, expires=180, meta={}), ['k1']),
                  metadata={'targets': envelope(targets('targets', files, version=1), ['k1'])}, artifacts=files)
    simple['snapshot']['signed']['meta'] = {'targets': dict(version=1, length=len(canonical(simple['metadata']['targets'])), sha256=hashlib.sha256(canonical(simple['metadata']['targets'])).hexdigest())}
    simple['snapshot'] = envelope(simple['snapshot']['signed'], ['k1'])
    (ws / 'tests/fixtures/single_repository.json').write_text(json.dumps({'anchors': {'tools': root}, 'request': dict(
        id='lint-1', expected_version=0, at=10, bundles={'tools': simple}, requested=[dict(repo='tools', path='tools/lint', sha256=sha('lint 0.9'))])}, indent=1) + '\n')
    cases = build_cases()
    for old in (TASK / 'grader/cases').glob('*.json'): old.unlink()
    for name, case in cases.items():
        (TASK / 'grader/cases' / (name + '.json')).write_text(json.dumps(case, separators=(',', ':')) + '\n')
    print(sorted(cases))
