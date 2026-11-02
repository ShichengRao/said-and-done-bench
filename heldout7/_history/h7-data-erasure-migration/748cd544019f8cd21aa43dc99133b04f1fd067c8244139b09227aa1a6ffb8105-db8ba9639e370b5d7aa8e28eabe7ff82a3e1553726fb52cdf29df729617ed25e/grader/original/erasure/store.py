"""Immutable overlay store, CDC head replay and original logical views."""
import json
from pathlib import Path

FILES = ('catalog', 'changes', 'holds', 'identity', 'policies', 'requests')


def load(root):
    return {name: json.loads((Path(root) / ('%s.json' % name)).read_text()) for name in FILES}


def replay(catalog, changes):
    """Return (nodes, heads) after applying CDC events watermark < seq <= cutover."""
    nodes = {}
    heads = dict(catalog['heads'])

    def insert(node):
        if node['id'] in nodes and nodes[node['id']] != node:
            raise ValueError('conflicting definitions for node %s' % node['id'])
        nodes[node['id']] = node

    for node in catalog['nodes']:
        insert(node)

    def check_heads():
        for obj, node in heads.items():
            if node not in nodes or nodes[node]['object'] != obj:
                raise ValueError('invalid head %s -> %s' % (obj, node))

    check_heads()
    events = {}
    for event in changes:
        if event['seq'] > catalog['cutover']:
            continue
        if event['seq'] in events and events[event['seq']] != event:
            raise ValueError('conflicting CDC events at seq %s' % event['seq'])
        events[event['seq']] = event
    for seq, event in sorted(events.items()):
        if seq <= catalog['watermark']:
            continue
        if event['op'] == 'delete':
            heads.pop(event['object'], None)
            continue
        if event['op'] == 'put':
            insert(event['value'])
            target = event['value']['id']
        else:
            target = event['node']
        if target not in nodes or nodes[target]['object'] != event['object']:
            raise ValueError('invalid CDC head at seq %s' % seq)
        heads[event['object']] = target
    check_heads()
    original_views(nodes)  # validates parents and cycles across the whole store
    return nodes, heads


def original_views(nodes):
    """{node: {key: row}} overlaying parents in order, then own rows (tombstones kept)."""
    views, visiting = {}, set()

    def view(name):
        if name in views:
            return views[name]
        if name not in nodes or name in visiting:
            raise ValueError('missing node or cycle at %s' % name)
        visiting.add(name)
        merged = {}
        for parent in nodes[name]['parents']:
            merged.update(view(parent))
        merged.update({row['key']: row for row in nodes[name]['rows']})
        visiting.remove(name)
        views[name] = merged
        return merged

    for name in nodes:
        view(name)
    return views
