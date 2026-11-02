"""Durable two-surge controller; the planner searches finite adversarial cutovers."""
import copy
import itertools
import json
import sqlite3
from contextlib import contextmanager
from functools import lru_cache

NOMINAL_ONLY = False
PROJECTED_ELIGIBILITY = False
IGNORE_EXISTING_HANDOFFS = False
BUDGET_PER_PENDING = False


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


@contextmanager
def transaction(path):
    db = sqlite3.connect(path, timeout=30)
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY,value TEXT)')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def load(db):
    row = db.execute('SELECT value FROM control WHERE id=1').fetchone()
    if row is None:
        raise ValueError('uninitialized')
    return json.loads(row[0])


def save(db, state):
    db.execute('INSERT OR REPLACE INTO control VALUES(1,?)', (canonical(state),))


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


def initialize(path, configuration):
    with transaction(path) as db:
        row = db.execute('SELECT value FROM control WHERE id=1').fetchone()
        if row:
            state = json.loads(row[0])
            if state['configuration'] != configuration:
                raise ValueError('different configuration')
        else:
            if not valid_inventory(configuration, configuration['initial']):
                raise ValueError('invalid inventory')
            state = dict(configuration=copy.deepcopy(configuration), version=0, epoch=0,
                         observed=copy.deepcopy(configuration['initial']), pending={}, handoffs={}, done=[],
                         quarantine=[], faults_left=0, rollouts=None, locations={}, attempts={}, settled={}, requests={})
            save(db, state)
        return summary(state)


def inspect(path):
    with transaction(path) as db:
        return summary(load(db))


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
                if NOMINAL_ONLY or left == 0 or visit(position, done, tuple(sorted((*bad, target))), left - 1):
                    return True
        return False

    return visit(initial, finished, tuple(sorted(quarantine)), budget)


def completion_preserved(state, handoffs):
    unknown = sorted(service for service, h in handoffs.items() if h['phase'] == 'starting')
    maximum = len(unknown) if BUDGET_PER_PENDING and state['faults_left'] else state['faults_left']
    for nfailed in range(min(len(unknown), maximum) + 1):
        for failed in itertools.combinations(unknown, nfailed):
            if NOMINAL_ONLY and failed:
                continue
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
            if PROJECTED_ELIGIBILITY:
                occupied -= {h['source'] for h in state['handoffs'].values()}
            if target in occupied | reserved | set(state['quarantine']):
                continue
            if len(occupied) + len(reserved) + 1 > state['configuration']['capacity']:
                continue
            attempt = state['attempts'].get(service, 0) + 1
            handoff = dict(source=ticket['source'], target=target, phase='starting', attempt=attempt)
            considered = {} if IGNORE_EXISTING_HANDOFFS else copy.deepcopy(state['handoffs'])
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


def apply(path, request):
    with transaction(path) as db:
        state = load(db)
        q = copy.deepcopy(request)
        identity, payload = q['id'], canonical(q)
        if identity in state['requests']:
            prior = state['requests'][identity]
            if prior['payload'] != payload:
                raise ValueError('conflicting request reuse')
            return copy.deepcopy(prior['response'])
        if q['expected_version'] != state['version']:
            raise ValueError('version conflict')
        if q['kind'] == 'install':
            extra = install(state, q)
        elif q['kind'] == 'dispatch':
            extra = dispatch(state)
        elif q['kind'] == 'receipt':
            extra = receipts(state, q)
        else:
            raise ValueError('unknown request kind')
        state['version'] += 1
        response = {**summary(state), **extra}
        state['requests'][identity] = dict(payload=payload, response=copy.deepcopy(response))
        save(db, state)
        return response
