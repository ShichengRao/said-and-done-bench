"""Literal schedule enumeration and immutable request transitions, independent of SQLite."""
import copy
import itertools
import json


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def safe(configuration, inventory):
    if set(inventory) != set(configuration['nodes']):
        return False
    occupied = [(node, value) for node, value in inventory.items() if value is not None]
    for node, value in occupied:
        if value['service'] not in configuration['services']:
            return False
        if configuration['services'][value['service']]['size'] > configuration['nodes'][node]['capacity']:
            return False
    for rack, capacity in configuration['rack_capacity'].items():
        demand = sum(configuration['services'][value['service']]['size'] for node, value in occupied
                     if configuration['nodes'][node]['rack'] == rack)
        if demand > capacity:
            return False
    for service, limits in configuration['services'].items():
        placements = [node for node, value in occupied if value['service'] == service]
        if len(placements) < limits['min_ready']:
            return False
        if len({configuration['nodes'][node]['zone'] for node in placements}) < limits['min_zones']:
            return False
    return True


def effect(inventory, action):
    node = action['node']
    identity = {key: action[key] for key in ('service', 'image')}
    if action['op'] == 'start' and inventory[node] is None:
        return {**inventory, node: identity}
    if action['op'] == 'stop' and inventory[node] == identity:
        return {**inventory, node: None}
    raise ValueError('operation precondition')


def schedules(configuration, inventory, actions, target, completed=()):
    """Enumerate literal orders; no memoized completed-set search is used."""
    completed = set(completed)
    remaining = sorted(set(actions) - completed)
    if not safe(configuration, inventory) or not safe(configuration, target):
        return []
    answers = []
    for order in itertools.permutations(remaining):
        seen = set(completed)
        current = inventory
        for identity in order:
            action = actions[identity]
            if not set(action['depends']) <= seen:
                break
            try:
                current = effect(current, action)
            except ValueError:
                break
            if not safe(configuration, current):
                break
            seen.add(identity)
        else:
            if current == target:
                answers.append(order)
    return answers


def subset_safe(configuration, observed, actions):
    if len({action['node'] for action in actions}) != len(actions):
        return False
    # Including all starts and no stops also checks physical reservations.
    for count in range(len(actions) + 1):
        for subset in itertools.combinations(actions, count):
            current = observed
            try:
                for action in subset:
                    current = effect(current, action)
            except ValueError:
                return False
            if not safe(configuration, current):
                return False
    return True


def dispatch(state):
    waiting = [entry['action'] for entry in state['pending'].values()]
    selected = []
    for identity in sorted(state['actions']):
        if len(waiting) + len(selected) >= state['configuration']['max_inflight']:
            break
        action = state['actions'][identity]
        if identity in state['done'] or identity in waiting or not set(action['depends']) <= set(state['done']):
            continue
        hypothetical = waiting + selected + [identity]
        commands = [state['actions'][name] for name in hypothetical]
        if not subset_safe(state['configuration'], state['observed'], commands):
            continue
        projected = state['observed']
        for command in commands:
            projected = effect(projected, command)
        if not schedules(state['configuration'], projected, state['actions'], state['target'],
                         set(state['done']) | set(hypothetical)):
            continue
        selected.append(identity)
    return selected


def summary(state):
    return copy.deepcopy({key: state[key] for key in ('version', 'epoch', 'observed', 'pending', 'done', 'target')})


def initialize(configuration):
    if not safe(configuration, configuration['initial']):
        raise ValueError('unsafe initial')
    return dict(configuration=copy.deepcopy(configuration), version=0, epoch=0,
                observed=copy.deepcopy(configuration['initial']), pending={}, done=[], target=None,
                actions={}, attempts={}, settled={}, requests={})


def transition(state, request):
    """Return a new state/response, or reject without altering either argument."""
    identity = request['id']
    if identity in state['requests']:
        payload, response = state['requests'][identity]
        if payload != encoded(request):
            raise ValueError('request identity conflict')
        return copy.deepcopy(state), copy.deepcopy(response)
    if request['expected_version'] != state['version']:
        raise ValueError('version conflict')
    new = copy.deepcopy(state)
    kind = request['kind']
    extra = {}
    if kind == 'install':
        if request['epoch'] <= state['epoch']:
            raise ValueError('epoch not newer')
        actions = {action['id']: copy.deepcopy(action) for action in request['actions']}
        if len(actions) != len(request['actions']):
            raise ValueError('duplicate action')
        for name, action in actions.items():
            if name in action['depends'] or set(action['depends']) - set(actions):
                raise ValueError('dependency reference')
            if action['node'] not in new['configuration']['nodes'] or action['service'] not in new['configuration']['services']:
                raise ValueError('resource reference')
        if not schedules(new['configuration'], request['observed'], actions, request['target']):
            raise ValueError('no complete safe order')
        new.update(epoch=request['epoch'], observed=copy.deepcopy(request['observed']),
                   target=copy.deepcopy(request['target']), actions=actions, done=[], pending={},
                   attempts={}, settled={})
        extra['installed'] = True
    elif kind == 'dispatch':
        created = []
        for name in dispatch(state):
            attempt = new['attempts'].get(name, 0) + 1
            new['attempts'][name] = attempt
            token = f"{new['epoch']}:{name}:{attempt}"
            new['pending'][token] = {'action': name, 'attempt': attempt}
            created.append(token)
        extra['created'] = created
    elif kind == 'receipt':
        entries = []
        for receipt in request['receipts']:
            token, success = receipt['token'], receipt['success']
            if token in new['settled']:
                if new['settled'][token] != success:
                    raise ValueError('receipt outcome conflict')
                disposition = 'replayed'
            elif token not in new['pending']:
                disposition = 'stale'
            else:
                name = new['pending'].pop(token)['action']
                if success:
                    new['observed'] = effect(new['observed'], new['actions'][name])
                    new['done'] = sorted(new['done'] + [name])
                new['settled'][token] = success
                disposition = 'applied' if success else 'failed'
            entries.append({'token': token, 'disposition': disposition})
        extra['receipts'] = entries
    else:
        raise ValueError('request kind')
    new['version'] += 1
    response = {**summary(new), **extra}
    new['requests'][identity] = (encoded(request), copy.deepcopy(response))
    return new, response
