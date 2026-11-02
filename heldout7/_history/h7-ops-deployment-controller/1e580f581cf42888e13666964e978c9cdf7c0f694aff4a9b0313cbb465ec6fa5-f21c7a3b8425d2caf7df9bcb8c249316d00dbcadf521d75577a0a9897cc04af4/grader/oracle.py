"""Trusted in-memory rollout oracle: the reference controller logic (from the h6-ops-rollout honest
controller) without SQLite. Never imports candidate code. A rejected request changes nothing."""
import copy
import itertools
import json
from functools import lru_cache


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def summary(state):
    keys = ('version', 'epoch', 'observed', 'pending', 'handoffs', 'done', 'quarantine', 'faults_left', 'rollouts')
    result = {key: copy.deepcopy(state[key]) for key in keys}
    result['complete'] = state['rollouts'] is not None and len(state['done']) == len(state['rollouts'])
    return result


def valid_inventory(configuration, observed):
    if set(observed) != set(configuration['nodes']):
        return False
    present = [v for v in observed.values() if v is not None]
    return len(present) <= configuration['capacity'] and len({v['service'] for v in present}) == len(present)


def winning(state, locations, completed, quarantine, budget):
    services = tuple(sorted(state['rollouts']))
    routes = tuple(tuple(state['rollouts'][service]['targets']) for service in services)
    nodes = tuple(state['configuration']['nodes'])
    initial = tuple(locations[service] for service in services)
    finished = sum(1 << i for i, service in enumerate(services) if service in completed)
    enough_surge = state['configuration']['capacity'] > len(services)

    @lru_cache(None)
    def visit(position, done, bad, left):
        if done == (1 << len(services)) - 1:
            return True
        if not enough_surge:
            return False
        free = set(nodes) - set(position) - set(bad)
        for i, targets in enumerate(routes):
            if done & (1 << i):
                continue
            for target in targets:
                if target not in free:
                    continue
                after = list(position)
                after[i] = target
                if not visit(tuple(after), done | (1 << i), bad, left):
                    continue
                if left == 0 or visit(position, done, tuple(sorted((*bad, target))), left - 1):
                    return True
        return False

    return visit(initial, finished, tuple(sorted(quarantine)), budget)


def completion_preserved(state, handoffs):
    unknown = sorted(service for service, h in handoffs.items() if h['phase'] == 'starting')
    maximum = state['faults_left']
    for nfailed in range(min(len(unknown), maximum) + 1):
        for failed in itertools.combinations(unknown, nfailed):
            locations = dict(state['locations'])
            completed = set(state['done'])
            bad = set(state['quarantine'])
            for service, handoff in handoffs.items():
                if service in failed:
                    bad.add(handoff['target'])
                else:
                    locations[service] = handoff['target']
                    completed.add(service)
            remaining = max(0, state['faults_left'] - nfailed)
            if not winning(state, locations, completed, bad, remaining):
                return False
    return True


def install(state, request):
    if request['epoch'] <= state['epoch'] or state['pending'] or state['handoffs']:
        raise ValueError('epoch not drained and newer')
    cfg = state['configuration']
    observed = copy.deepcopy(request['observed'])
    if not valid_inventory(cfg, observed):
        raise ValueError('invalid fenced inventory')
    tickets = request['rollouts']
    rollouts = {t['service']: copy.deepcopy(t) for t in tickets}
    if len(rollouts) != len(tickets):
        raise ValueError('duplicate service')
    present = {v['service']: node for node, v in observed.items() if v is not None}
    if set(present) != set(rollouts):
        raise ValueError('tickets do not cover fenced services')
    for service, ticket in rollouts.items():
        source, targets = ticket['source'], ticket['targets']
        if (source != present[service] or observed[source]['image'] != ticket['old_image']
                or ticket['new_image'] == ticket['old_image'] or len(set(targets)) != len(targets)
                or source in targets or set(targets) - set(cfg['nodes'])):
            raise ValueError('invalid ticket')
        ticket['targets'] = sorted(targets)
    proposed = copy.deepcopy(state)
    proposed.update(epoch=request['epoch'], observed=observed, rollouts=rollouts, done=[], quarantine=[],
                    faults_left=request['fault_budget'], locations=present, pending={}, handoffs={}, attempts={}, settled={})
    if not winning(proposed, present, set(), set(), request['fault_budget']):
        raise ValueError('no guaranteed completion')
    state.update(proposed)
    return {'installed': True}


def dispatch(state):
    if state['rollouts'] is None:
        return {'created': []}
    created = []
    limit = state['configuration']['max_handoffs']
    for service, handoff in sorted(state['handoffs'].items()):
        if len(state['pending']) >= limit:
            break
        if handoff['phase'] != 'ready':
            continue
        ticket = state['rollouts'][service]
        token = f"{state['epoch']}:{service}:retire:{handoff['attempt']}"
        state['pending'][token] = dict(op='retire', service=service, source=handoff['source'],
                                      target=handoff['target'], image=ticket['old_image'], attempt=handoff['attempt'])
        handoff['phase'] = 'retiring'
        created.append(token)
    for service, ticket in sorted(state['rollouts'].items()):
        if len(state['pending']) >= limit or len(state['handoffs']) >= limit:
            break
        if service in state['done'] or service in state['handoffs']:
            continue
        for target in ticket['targets']:
            occupied = {node for node, value in state['observed'].items() if value is not None}
            reserved = {p['target'] for p in state['pending'].values() if p['op'] == 'start'}
            if target in occupied | reserved | set(state['quarantine']):
                continue
            if len(occupied) + len(reserved) + 1 > state['configuration']['capacity']:
                continue
            attempt = state['attempts'].get(service, 0) + 1
            handoff = dict(source=ticket['source'], target=target, phase='starting', attempt=attempt)
            considered = copy.deepcopy(state['handoffs'])
            considered[service] = handoff
            if not completion_preserved(state, considered):
                continue
            token = f"{state['epoch']}:{service}:start:{attempt}"
            state['attempts'][service] = attempt
            state['handoffs'][service] = handoff
            state['pending'][token] = dict(op='start', service=service, source=ticket['source'],
                                          target=target, image=ticket['new_image'], attempt=attempt)
            created.append(token)
            break
    return {'created': created}


def receipts(state, request):
    result = []
    for receipt in request['receipts']:
        token, success = receipt['token'], receipt['success']
        if token in state['settled']:
            if state['settled'][token] != success:
                raise ValueError('conflicting settled receipt')
            disposition = 'replayed'
        elif token not in state['pending']:
            disposition = 'stale'
        else:
            command = state['pending'][token]
            service = command['service']
            if command['op'] == 'retire' and not success:
                raise ValueError('retirements are reliable')
            if command['op'] == 'start':
                if success:
                    state['observed'][command['target']] = dict(service=service, image=command['image'])
                    state['handoffs'][service]['phase'] = 'ready'
                else:
                    if state['faults_left'] == 0:
                        raise ValueError('fault allowance exhausted')
                    state['faults_left'] -= 1
                    state['quarantine'] = sorted(set(state['quarantine']) | {command['target']})
                    del state['handoffs'][service]
            else:
                state['observed'][command['source']] = None
                state['locations'][service] = command['target']
                state['done'] = sorted(set(state['done']) | {service})
                del state['handoffs'][service]
            del state['pending'][token]
            state['settled'][token] = success
            disposition = 'applied' if success else 'failed'
        result.append(dict(token=token, disposition=disposition))
    return {'receipts': result}


class Controller:
    def __init__(self, configuration):
        if not valid_inventory(configuration, configuration['initial']):
            raise ValueError('invalid inventory')
        self.state = dict(configuration=copy.deepcopy(configuration), version=0, epoch=0,
                          observed=copy.deepcopy(configuration['initial']), pending={}, handoffs={}, done=[],
                          quarantine=[], faults_left=0, rollouts=None, locations={}, attempts={}, settled={}, requests={})

    def inspect(self):
        return summary(self.state)

    def apply(self, request):
        state = copy.deepcopy(self.state); q = copy.deepcopy(request)
        identity, payload = q['id'], canonical(q)
        if identity in state['requests']:
            if state['requests'][identity]['payload'] != payload:
                raise ValueError('conflicting request reuse')
            return copy.deepcopy(state['requests'][identity]['response'])
        if q['expected_version'] != state['version']:
            raise ValueError('version conflict')
        handler = {'install': lambda: install(state, q), 'dispatch': lambda: dispatch(state), 'receipt': lambda: receipts(state, q)}.get(q['kind'])
        if handler is None:
            raise ValueError('unknown request kind')
        extra = handler(); state['version'] += 1
        response = {**summary(state), **extra}
        state['requests'][identity] = dict(payload=payload, response=copy.deepcopy(response))
        self.state = state
        return response


def semantic(x):
    """Documented fields only; extra metadata on records is permitted by the README."""
    if x is None:
        return None
    result = {k: copy.deepcopy(x[k]) for k in ('version', 'epoch', 'done', 'quarantine', 'faults_left', 'complete')}
    result['observed'] = {n: None if v is None else {k: v[k] for k in ('service', 'image')} for n, v in x['observed'].items()}
    result['pending'] = {t: {k: p[k] for k in ('op', 'service', 'source', 'target', 'image', 'attempt')} for t, p in x['pending'].items()}
    result['handoffs'] = {s: {k: h[k] for k in ('source', 'target', 'phase', 'attempt')} for s, h in x['handoffs'].items()}
    result['rollouts'] = None if x['rollouts'] is None else {s: {k: t[k] for k in ('service', 'source', 'old_image', 'new_image', 'targets')} for s, t in x['rollouts'].items()}
    if 'created' in x:
        result['created'] = list(x['created'])
    if 'receipts' in x:
        result['receipts'] = [{'token': r['token'], 'disposition': r['disposition']} for r in x['receipts']]
    return result


def run_case(case):
    """Expected outcomes: initialize summary, then per step a semantic response, 'error' or an inspect summary."""
    controller = Controller(case['configuration']); outcomes = [{'initialize': semantic(controller.inspect())}]
    for step in case['steps']:
        if step == 'inspect':
            outcomes.append({'inspect': semantic(controller.inspect())}); continue
        try:
            outcomes.append({'apply': semantic(controller.apply(step))})
        except ValueError:
            outcomes.append({'apply': 'error'})
    return outcomes


def expected_report(rollout):
    controller = Controller(rollout['configuration']); results = []
    for request in rollout['requests']:
        try:
            results.append({'id': request['id'], 'accepted': True, 'response': controller.apply(request)})
        except ValueError:
            results.append({'id': request['id'], 'accepted': False, 'response': None})
    return {'rollout_id': rollout['rollout_id'], 'results': results, 'final': controller.inspect()}


def report_errors(record, expected):
    """Compare a delivered report with the expected one on documented fields."""
    if not isinstance(record, dict) or not isinstance(record.get('results'), list):
        return ['report is not an object with results']
    errors = []
    if record.get('rollout_id') != expected['rollout_id']:
        errors.append('incorrect rollout_id')
    got = record['results']
    if [r.get('id') if isinstance(r, dict) else None for r in got] != [r['id'] for r in expected['results']]:
        return errors + ['results do not list every rollout request in order']
    for mine, want in zip(got, expected['results']):
        try:
            same = mine.get('accepted') is want['accepted'] and semantic(mine.get('response')) == semantic(want['response'])
        except (KeyError, TypeError, AttributeError):
            same = False
        if not same:
            errors.append(f"result for {want['id']} differs from the controller replay"); break
    try:
        if semantic(record.get('final')) != semantic(expected['final']):
            errors.append('final state differs from the controller replay')
    except (KeyError, TypeError, AttributeError):
        errors.append('final state unreadable')
    return errors
