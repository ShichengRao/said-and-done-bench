"""Trusted delivery-certificate oracle; never imports candidate code.

Enumerates literal interleavings of the sealed exports, then recomputes every
compare-and-swap predicate and captured provenance from earlier recorded
successes (no incremental replay state is shared with any implementation).
"""
import copy
import json
from pathlib import Path

FIELDS = ('receipt', 'copy', 'lineage', 'record', 'captured_owner', 'captured_version',
          'credential', 'ancestry', 'audience')


def read_batch(root):
    root = Path(root)
    read = lambda name: json.loads((root / name).read_text())
    meta = read('batch.json')
    return {'meta': meta, 'records': read('records.json'), 'credentials': read('credentials.json'),
            'exports': {name: read('exports/%s.json' % name) for name in meta['exports']},
            'ordering': read('ordering.json')}


def write_batch(root, batch):
    root = Path(root); (root / 'exports').mkdir(parents=True, exist_ok=True)
    dump = lambda name, value: (root / name).write_text(json.dumps(value, indent=2) + '\n')
    dump('batch.json', batch['meta']); dump('records.json', batch['records'])
    dump('credentials.json', batch['credentials']); dump('ordering.json', batch['ordering'])
    for name, export in batch['exports'].items():
        dump('exports/%s.json' % name, export)


def _shuffles(streams):
    if not any(streams):
        yield (); return
    for i, stream in enumerate(streams):
        if stream:
            rest = list(streams); rest[i] = stream[1:]
            for tail in _shuffles(rest):
                yield (stream[0],) + tail


def histories(batch):
    """Return [(order, deliveries)] for every history consistent with the evidence."""
    streams = [[e['id'] for e in batch['exports'][n]['events']] for n in batch['meta']['exports']]
    by = {e['id']: e for n in batch['meta']['exports'] for e in batch['exports'][n]['events']}
    issued = {c['id']: c for c in batch['credentials']['issued']}
    slots0 = batch['credentials']['slots']
    if len(by) + len(issued) != sum(map(len, streams)) + len(batch['credentials']['issued']) or set(by) & set(issued):
        raise ValueError('duplicate identity')
    defs = {**issued, **{k: e for k, e in by.items() if e['kind'] == 'grant'}}
    edges = [(a['earlier'], a['later']) for a in batch['ordering']['attestations']]
    for e in by.values():
        if e['kind'] == 'copy' and e['source']['kind'] == 'copy':
            edges.append((e['source']['id'], e['id']))
        if e['kind'] == 'receipt':
            edges.append((e['copy'], e['id']))
    if any(a not in by or b not in by for a, b in edges):
        raise ValueError('unknown ordering endpoint')
    accepted = []
    for order in _shuffles(streams):
        pos = {n: i for i, n in enumerate(order)}
        if any(pos[a] >= pos[b] for a, b in edges):
            continue

        def record_at(rec, at):
            writes = [by[n] for n in order[:at] if by[n]['kind'] == 'owner_change' and by[n]['record'] == rec and by[n]['succeeded']]
            base = batch['records'][rec]
            return (writes[-1]['new_owner'] if writes else base['owner'], base['version'] + len(writes))

        def slot_at(slot, at):
            writes = [by[n] for n in order[:at] if by[n]['kind'] in ('grant', 'revoke') and by[n]['slot'] == slot and by[n]['succeeded']]
            base = slots0[slot]
            current = (writes[-1]['id'] if writes[-1]['kind'] == 'grant' else None) if writes else base['current']
            return base['generation'] + len(writes), current

        def live(name, at):
            if name not in defs:
                return False
            if name not in issued and (not by[name]['succeeded'] or pos[name] >= at):
                return False
            if slot_at(defs[name]['slot'], at)[1] != name:
                return False
            return defs[name]['parent'] is None or live(defs[name]['parent'], at)

        ok = True
        for at, name in enumerate(order):
            e = by[name]
            if e['kind'] == 'owner_change':
                pred = record_at(e['record'], at)[1] == e['expected_version']
            elif e['kind'] in ('grant', 'revoke'):
                pred = slot_at(e['slot'], at)[0] == e['expected_generation']
                if e['kind'] == 'grant':
                    if e['parent'] is None:
                        pred = pred and e['owner'] == e['issuer']
                    else:
                        p = defs.get(e['parent'])
                        pred = pred and p is not None and live(e['parent'], at) and p['delegable'] and p['audience'] == e['issuer'] and p['owner'] == e['owner']
            else:
                continue
            if pred != e['succeeded']:
                ok = False; break
        if not ok:
            continue
        deliveries = []
        for name in order:
            r = by[name]
            if r['kind'] != 'receipt':
                continue
            lineage = [r['copy']]; root = by[r['copy']]
            while root['source']['kind'] == 'copy':
                root = by[root['source']['id']]; lineage.insert(0, root['id'])
            owner, version = record_at(root['source']['id'], pos[root['id']])
            cred = slot_at(root['slot'], pos[root['id']])[1]
            ancestry = []; node = cred
            while node is not None:
                ancestry.insert(0, node); node = defs[node]['parent']
            at = pos[name]
            authorized = (cred is not None and defs[cred]['owner'] == owner and defs[cred]['audience'] == r['audience']
                          and all(slot_at(defs[n]['slot'], at)[1] == n for n in ancestry))
            deliveries.append({'receipt': name, 'copy': r['copy'], 'lineage': lineage, 'record': root['source']['id'],
                               'captured_owner': owner, 'captured_version': version, 'credential': cred,
                               'ancestry': ancestry, 'audience': r['audience'], 'authorized': authorized})
        accepted.append((order, deliveries))
    accepted.sort(key=lambda row: row[0])
    return accepted


def summary(batch):
    rows = histories(batch)
    safe = [o for o, d in rows if all(x['authorized'] for x in d)]
    return {'consistent': len(rows), 'all_authorized': len(safe), 'some_unauthorized': len(rows) - len(safe),
            'first_all_authorized': list(safe[0]) if safe else None,
            'first_unauthorized': next((list(o) for o, d in rows if not all(x['authorized'] for x in d)), None)}


def expected_certificate(batch):
    """The only supportable certificate, or None when the evidence does not establish one."""
    rows = histories(batch)
    if not rows or not all(x['authorized'] for _, d in rows for x in d):
        return None
    views = {json.dumps(sorted(({k: x[k] for k in FIELDS} for x in d), key=lambda x: x['receipt']), sort_keys=True) for _, d in rows}
    if len(views) != 1:
        return None
    return {'batch': batch['meta']['batch'], 'customer': batch['meta']['customer'], 'deliveries': json.loads(views.pop())}


def validate_certificate(certificate, batch):
    expected = expected_certificate(batch)
    if expected is None:
        return ['batch evidence does not establish authorization for every delivery']
    if not isinstance(certificate, dict):
        return ['certificate is not an object']
    errors = []
    for key in ('batch', 'customer'):
        if certificate.get(key) != expected[key]:
            errors.append('incorrect ' + key)
    if certificate.get('deliveries') != expected['deliveries']:
        errors.append('deliveries differ from the established provenance')
    return errors


def counterpart(batch):
    """Nearby feasible batch: three further signed ordering attestations (author-only)."""
    other = copy.deepcopy(batch)
    other['ordering']['attestations'] += [
        {'earlier': 'b2', 'later': 'a3', 'signed_by': 'account-service notary', 'reference': 'NTR-X-1'},
        {'earlier': 'c3', 'later': 'b1', 'signed_by': 'delivery-service notary', 'reference': 'NTR-X-2'},
        {'earlier': 'b4', 'later': 'c4', 'signed_by': 'credential-service notary', 'reference': 'NTR-X-3'}]
    return other


def relabel(batch, prefix='z-'):
    """Rename every event and grant-created credential consistently."""
    text = json.dumps(batch)
    ids = [e['id'] for ex in batch['exports'].values() for e in ex['events']]
    for name in sorted(ids, key=len, reverse=True):
        text = text.replace('"%s"' % name, '"%s%s"' % (prefix, name))
    return json.loads(text)
