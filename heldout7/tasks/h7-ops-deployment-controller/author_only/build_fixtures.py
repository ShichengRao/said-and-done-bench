"""Author-only builder. Customer rollout = h6-ops-rollout input.json (author_only/source_input.json)
with order-preserving fictional renames. Grader cases record request sequences from the previous
behavior tests, driven adaptively by the trusted oracle (grader/oracle.py)."""
import copy, importlib.util, itertools, json
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('oracle', TASK / 'grader/oracle.py'); oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
SOURCE = json.loads((Path(__file__).with_name('source_input.json')).read_text())
SERVICES = {'A': 'api', 'B': 'billing', 'C': 'checkout', 'D': 'dispatcher'}
NODES = {n: 'edge-' + n for n in 'abcdxy'}
IMAGES = {'old': '2026.09.3', 'new': '2026.11.0'}

def rename(value):
    if isinstance(value, dict): return {rename_key(k): rename(v) for k, v in value.items()}
    if isinstance(value, list): return [rename(v) for v in value]
    if isinstance(value, str):
        if value in SERVICES: return SERVICES[value]
        if value in NODES: return NODES[value]
        if value in IMAGES: return IMAGES[value]
        if value.count(':') == 3:
            epoch, service, op, attempt = value.split(':'); return ':'.join([epoch, SERVICES[service], op, attempt])
    return value
def rename_key(k): return NODES.get(k, SERVICES.get(k, k))

CONFIG = rename(SOURCE['configuration'])
INSTALL = rename(SOURCE['install'])
TRACE = rename(SOURCE['trace'])
ROLLOUT = {'rollout_id': 'northwind-ferries-2026-11', 'configuration': CONFIG,
           'requests': [dict(id='install-1', expected_version=0, kind='install', **INSTALL)] + TRACE}

class Driver:
    def __init__(self, cfg, plan=None):
        self.c = oracle.Controller(copy.deepcopy(cfg)); self.cfg = cfg; self.steps = []
        if plan is not None: self.call('install', **plan)
    def raw(self, request, expect_error=False):
        self.steps.append(copy.deepcopy(request))
        try:
            out = self.c.apply(request); assert not expect_error, request; return out
        except ValueError:
            assert expect_error, request; self.steps.append('inspect'); return None
    def call(self, kind, expect_error=False, **kw):
        v = self.c.inspect()['version']; return self.raw(dict(id=f'request-{v}', expected_version=v, kind=kind, **kw), expect_error)
    def receipts(self, pairs, expect_error=False):
        return self.call('receipt', expect_error, receipts=[dict(token=t, success=s) for t, s in pairs])
    def finish(self, limit=20, reverse=True):
        for _ in range(limit):
            if self.c.inspect()['complete']: break
            pending = self.call('dispatch')['pending']; assert pending
            self.receipts([(t, True) for t in (reversed(pending) if reverse else pending)])
        assert self.c.inspect()['complete']; self.steps.append('inspect')
    def case(self, note): return {'note': note, 'configuration': self.cfg, 'steps': self.steps}

def build():
    cases = {}
    for outcomes in [(True, True), (False, True), (True, False)]:
        d = Driver(CONFIG, INSTALL); first = d.call('dispatch')['created']; d.receipts(zip(first, outcomes)); d.finish()
        cases['initial_outcomes_' + ''.join('S' if o else 'F' for o in outcomes)] = d.case('each allowed outcome of the two initial starts completes')
    d = Driver(CONFIG, INSTALL)
    for _ in range(2):
        tokens = d.call('dispatch')['created']; d.receipts([(t, True) for t in tokens])
    tokens = d.call('dispatch')['created']; assert tokens == ['1:dispatcher:start:1'], tokens
    d.receipts([(tokens[0], False)]); d.call('dispatch'); d.finish()
    cases['later_failure_covered'] = d.case('unused fault allowance covers a failure after both initial starts succeed')
    d = Driver(CONFIG, INSTALL); a, b = d.call('dispatch')['created']; d.receipts([(a, False), (b, False)], expect_error=True)
    d.receipts([(a, True), (b, True)]); tokens = d.call('dispatch')['created']; d.receipts([(tokens[0], True), (tokens[1], False)], expect_error=True)
    cases['whole_batch_rejections'] = d.case('second failure and retirement failure reject whole batches')
    d = Driver(CONFIG, INSTALL); a, b = d.call('dispatch')['created']; d.receipts([(a, True), (b, False)])
    new = dict(INSTALL, epoch=2); d.call('install', expect_error=True, **new)
    stop = d.call('dispatch')['created'][0]; d.receipts([(stop, True)]); d.call('install', **new); d.receipts([(a, False)]); d.steps.append('inspect')
    cases['fenced_epoch_requires_drained_handoffs'] = d.case('new epoch only after full drain; resets quarantine; old tokens stale')
    d = Driver(CONFIG, INSTALL)
    for change in ['nominal-only', 'own-source', 'source-identity', 'duplicate-ticket', 'target-unknown']:
        new = copy.deepcopy(INSTALL); new['epoch'] = 2
        if change == 'nominal-only':
            for t in new['rollouts']: t['targets'] = [{'api': 'edge-c', 'billing': 'edge-x', 'checkout': 'edge-y', 'dispatcher': 'edge-b'}[t['service']]]
        elif change == 'own-source': new['rollouts'][0]['targets'] = ['edge-a']
        elif change == 'source-identity': new['rollouts'][0]['old_image'] = 'different'
        elif change == 'duplicate-ticket': new['rollouts'][1] = copy.deepcopy(new['rollouts'][0])
        else: new['rollouts'][0]['targets'] = ['unknown']
        d.call('install', expect_error=True, **new)
    cases['invalid_or_unwinnable_installs'] = d.case('nominal-only routes and malformed tickets are rejected without changes')
    for index in range(12):
        cfg = copy.deepcopy(CONFIG); plan = copy.deepcopy(INSTALL)
        cfg['max_handoffs'] = 1 + index % 2; cfg['capacity'] = 4 + index % 3; plan['fault_budget'] = index % 2
        if index // 3 % 2: plan['rollouts'][index % 4]['targets'] = plan['rollouts'][index % 4]['targets'][:1]
        d = Driver(cfg)
        try:
            oracle.Controller(cfg).apply(dict(id='probe', expected_version=0, kind='install', **plan)); possible = True
        except ValueError: possible = False
        if possible: d.call('install', **plan); d.finish()
        else: d.call('install', expect_error=True, **plan)
        cases[f'generated_routes_{index:02d}'] = d.case('bounded capacity/window/budget/route variant')
    families = [
      (['a','b','c','d','x','y'],['A','B','C','D'],[['c','d','x','y'],['a','x'],['d','y'],['b','c','y']],6,2,1),
      (['a','b','c','d','x','y'],['A','B','C','D'],[['c','d','x','y'],['a','x'],['d','y'],['b','c','y']],5,1,1),
      (['a','b','c','d','x','y'],['A','B','C','D'],[['b','c','x','y'],['a','d','x','y'],['a','b','x','y'],['b','c','x','y']],6,2,1),
      (['u','v','w','p','q'],['s','t','r'],[['v','p'],['w','p','q'],['u','p','q']],5,2,1),
      (['u','v','p','q'],['s','t'],[['v','p'],['u','q']],4,2,1),
      (['u','v','w','p'],['s','t','r'],[['p'],['u','p'],['v','p']],4,1,0),
      (['u','p'],['s'],[['p']],2,1,0)]
    for index, (nodes, services, targets, capacity, window, budget) in enumerate(families):
        nn = {n: 'node' + str(len(nodes) - i if index % 2 else i) for i, n in enumerate(nodes)}
        sn = {s: 'worker' + str(len(services) - i if index % 2 else i) for i, s in enumerate(services)}
        observed = {nn[n]: None for n in nodes}; tickets = []
        for source, service, choices in zip(nodes, services, targets):
            observed[nn[source]] = {'service': sn[service], 'image': f'release-{index}'}
            tickets.append(dict(service=sn[service], source=nn[source], old_image=f'release-{index}', new_image=f'next-{index}', targets=[nn[n] for n in reversed(choices)]))
        cfg = dict(nodes=list(reversed(list(nn.values()))), capacity=capacity, max_handoffs=window, initial=observed)
        d = Driver(cfg, dict(epoch=7, observed=observed, rollouts=list(reversed(tickets)), fault_budget=budget)); failed = False
        for turn in range(30):
            if d.c.inspect()['complete']: break
            pending = d.call('dispatch')['pending']; assert pending
            token = sorted(pending, reverse=bool(index % 2))[0]; command = pending[token]; success = True
            if not failed and budget and command['op'] == 'start' and turn >= index % 3: success = False; failed = True
            d.receipts([(token, success)])
        assert d.c.inspect()['complete']; d.steps.append('inspect')
        cases[f'relabelled_family_{index}'] = d.case('one receipt at a time; delayed readiness/retirement with lexical relabelling')
    d = Driver(CONFIG, INSTALL); q = dict(id='same', expected_version=1, kind='dispatch'); d.raw(q); d.call('receipt', receipts=[])
    d.raw(copy.deepcopy(q)); d.raw({**q, 'expected_version': 3}, expect_error=True)
    d.raw(dict(id='reusable', expected_version=0, kind='dispatch'), expect_error=True); v = d.c.inspect()['version']
    d.raw(dict(id='reusable', expected_version=v, kind='dispatch'))
    again = dict(id='install-again', expected_version=v + 1, kind='install', **{**INSTALL, 'epoch': 2})
    d.raw(again, expect_error=True)
    cases['replay_binding'] = d.case('exact replay before CAS, conflicting ID reuse rejected, rejected ID not consumed')
    d = Driver(CONFIG, INSTALL); original = dict(id='install-again', expected_version=1, kind='install', **{**INSTALL, 'epoch': 2})
    d.raw(original); d.call('install', **{**INSTALL, 'epoch': 3}); d.raw(copy.deepcopy(original)); d.steps.append('inspect')
    cases['global_replay_across_epochs'] = d.case('exact global replay of an install survives a newer fenced epoch')
    empty = {'nodes': [], 'capacity': 0, 'max_handoffs': 2, 'initial': {}}
    d = Driver(empty, dict(epoch=1, observed={}, rollouts=[], fault_budget=0)); d.call('dispatch'); d.raw(copy.deepcopy(d.steps[0])); d.steps.append('inspect')
    cases['empty_rollout'] = d.case('empty rollout installs, completes and replays')
    return cases

if __name__ == '__main__':
    (TASK / 'workspace/data/rollout.json').write_text(json.dumps(ROLLOUT, indent=1) + '\n')
    cases = build()
    for old in (TASK / 'grader/cases').glob('*.json'): old.unlink()
    for name, case in cases.items():
        (TASK / 'grader/cases' / (name + '.json')).write_text(json.dumps(case, separators=(',', ':')) + '\n')
    report = oracle.expected_report(ROLLOUT)
    print(len(cases), 'cases;', 'customer final complete', report['final']['complete'], 'version', report['final']['version'],
          'rejected', [r['id'] for r in report['results'] if not r['accepted']])
