"""Author-only positional proof for h7-data-delivery-export. No replay engine, no candidate code.

Uses the five order predicates derived by hand from the recorded outcomes
(AUTHOR_PROOF.md) and the three authorization predicates, evaluated on event
positions of every interleaving of the three sealed exports.
"""
import json
from itertools import combinations
from pathlib import Path

A = ['c3', 'a2', 'a3', 'a4']   # account-service
B = ['b1', 'b2', 'b3', 'b4']   # delivery-service
C = ['c1', 'c2', 'a1', 'c4']   # credential-service


def interleavings():
    """Choose positions for A, then B among the rest; C fills the remainder."""
    slots = range(12)
    for pa in combinations(slots, 4):
        rest = [s for s in slots if s not in pa]
        for pb in combinations(rest, 4):
            pc = [s for s in rest if s not in pb]
            order = [None] * 12
            for names, positions in ((A, pa), (B, pb), (C, pc)):
                for n, p in zip(names, positions):
                    order[p] = n
            yield order


def consistent(p, extra=()):
    return (p['c2'] < p['b4']                      # signed attestation
            and p['c2'] < p['c3'] and p['a1'] < p['c3']   # c3 grant succeeded; a1 revoke(expected 1) failed
            and p['c3'] < p['c4'] < p['a4']               # c3 needs live c2; a4 denial only explained by c4
            and (p['b2'] < p['a2'] or p['a3'] < p['b2'])  # b2 expected version 1 failed
            and all(p[a] < p[b] for a, b in extra))


def authorized(p):
    return (p['c3'] < p['b1']                              # captured credential is c3 (not leaf0 / empty slot)
            and (p['b1'] < p['a2'] or p['a3'] < p['b1'])   # captured owner alpha
            and p['b4'] < p['c4'])                          # c2 still live at delivery


def run(extra=()):
    rows = []
    for order in interleavings():
        p = {n: i for i, n in enumerate(order)}
        if consistent(p, extra):
            rows.append((order, authorized(p)))
    rows.sort()
    safe = [o for o, ok in rows if ok]; unsafe = [o for o, ok in rows if not ok]
    return {'consistent': len(rows), 'all_authorized': len(safe), 'some_unauthorized': len(unsafe),
            'first_all_authorized': safe[0] if safe else None, 'first_unauthorized': unsafe[0] if unsafe else None}


if __name__ == '__main__':
    result = {
        'raw_interleavings': sum(1 for _ in interleavings()),
        'current_batch': run(),
        'counterpart_three_attestations': run([('b2', 'a3'), ('c3', 'b1'), ('b4', 'c4')]),
        'counterpart_owner_return_and_expiry': run([('a3', 'b1'), ('b4', 'c4')]),
        'violation_variant_delivery_before_renewal': run([('b4', 'c3')]),
    }
    out = Path(__file__).with_name('proof_result.json')
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: (v if not isinstance(v, dict) else {x: v[x] for x in ('consistent', 'all_authorized', 'some_unauthorized')}) for k, v in result.items()}))
