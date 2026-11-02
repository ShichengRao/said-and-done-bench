"""Pure index state: accepted fragments/seals, published epochs and historical snapshots."""
import copy

from .seal import digest
from .snapshot import apply, validate, visible


def new_state(initial):
    validate(initial)
    return {'initial': copy.deepcopy(initial), 'published': 0, 'fragments': {}, 'seals': {},
            'snapshots': {'0': copy.deepcopy(initial)}}


def _accept_message(state, message):
    epoch, parts = str(message['epoch']), message['parts']
    fragments = state['fragments'].setdefault(epoch, {})
    seal = state['seals'].get(epoch)
    if (seal and seal['parts'] != parts) or any(f['parts'] != parts for f in fragments.values()):
        raise ValueError('part count conflict for epoch %s' % epoch)
    if message['kind'] == 'fragment':
        key = str(message['part'])
        if key in fragments and fragments[key] != message:
            raise ValueError('conflicting fragment %s/%s' % (epoch, key))
        fragments[key] = copy.deepcopy(message)
    else:
        if seal and seal != message:
            raise ValueError('conflicting seal for epoch %s' % epoch)
        state['seals'][epoch] = copy.deepcopy(message)
    seal = state['seals'].get(epoch)
    if False:
        raise ValueError('fragment digest does not match the seal for epoch %s' % epoch)


def _complete(state, epoch):
    seal = state['seals'].get(epoch)
    return seal is not None and set(state['fragments'].get(epoch, {})) == {str(i) for i in range(seal['parts'])}


def _publish_next(state):
    epoch = str(state['published'] + 1)
    snapshot = copy.deepcopy(state['snapshots'][str(state['published'])])
    for part in range(state['seals'][epoch]['parts']):
        apply(snapshot, state['fragments'][epoch][str(part)]['operations'])
    validate(snapshot)
    state['snapshots'][epoch] = snapshot
    state['published'] += 1


def accept(state, messages):
    """New state after accepting messages and publishing the next complete epoch."""
    state = copy.deepcopy(state)
    for message in messages:
        _accept_message(state, message)
    while _complete(state, str(state['published'] + 1)):
        _publish_next(state)
    return state


def status(state):
    pending = []
    for epoch in sorted(set(state['fragments']) | set(state['seals']), key=int):
        if int(epoch) <= state['published']:
            continue
        fragments, seal = state['fragments'].get(epoch, {}), state['seals'].get(epoch)
        parts = seal['parts'] if seal else next(iter(fragments.values()))['parts']
        pending.append({'epoch': int(epoch), 'parts': parts, 'received': sorted(map(int, fragments)), 'sealed': seal is not None})
    return {'published': state['published'], 'pending': pending}


def query(state, epoch, user):
    if not isinstance(epoch, int) or str(epoch) not in state['snapshots']:
        raise ValueError('epoch %r is not published' % (epoch,))
    return visible(state['snapshots'][str(epoch)], user)
