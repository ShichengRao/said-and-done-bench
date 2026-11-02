"""Rollout controller: fenced installs, lexical dispatch with completion lookahead, atomic receipt batches."""
import copy

from deployctl.planner import completion_preserved, winning
from deployctl.store import canonical, load, save, summary, transaction, valid_inventory


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


def apply(path, request):
    with transaction(path) as db:
        state = load(db)
        q = copy.deepcopy(request)
        identity, payload = q['id'], canonical(q)
        if identity in state['requests']:
            return copy.deepcopy(state['requests'][identity]['response'])
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
