"""Author-only proof for h7-data-erasure-migration, independent of grader/oracle.py and workspace code.

Hand table from data/ (catalog at=20, watermark 10, cutover 13):
* CDC: seq 10 covered; 11 puts N (archive); 12 (duplicated identically) moves profile O -> R2;
  13 deletes staging; 30 is after cutover. Live heads: archive N, orders R1, profile R2.
* Identity: t/reused is old-person on [0,10), new-person from 10. Request erase-old covers
  old-person through 5, so B.x (at 2) and U.unused (at 2) are erased; S.late (at 7) and R2.new
  (at 12, new-person) are not; tenant `other` rows are unrelated.
* Policies at 20: S rev1 (deny) superseded by approved rev2 (allow, cost 4, effective 15); rev3
  is an unapproved draft (cost 1); rev4 (cost 0) only takes effect at 30. B is denied.
* Holds: legal-H active on H (retains H and B); expired-S ended at 10.
"""
import json
from itertools import combinations
from pathlib import Path

# node: (parents in order, {key: (label, erased)})
NODES = {'B': ([], {'x': ('B.x', True), 'q': ('B.q', False)}), 'S': (['B'], {'late': ('S.late', False)}),
         'C': ([], {'x': ('C.x', False), 'c': ('C.c', False)}), 'R1': (['C', 'S'], {}),
         'R2': (['S'], {'new': ('R2.new', False)}), 'H': (['B'], {'evidence': ('H.evidence', False)}),
         'O': ([], {'old': ('O.old', False)}), 'U': ([], {'unused': ('U.unused', True)}),
         'X': (['B'], {}), 'N': ([], {'current': ('N.current', False)})}
HEADS = {'archive': 'N', 'orders': 'R1', 'profile': 'R2'}
POLICY = {'B': (False, 1), 'C': (True, 8), 'R2': (True, 3), 'O': (True, 8), 'X': (True, 8), 'S': (True, 4),
          'R1': (True, 3), 'H': (True, 8), 'U': (True, 8), 'N': (True, 8)}
HELD = {'H', 'B'}
TOMB = ('<tombstone>', False)


def original(name):
    parents, rows = NODES[name]; view = {}
    for p in parents:
        view.update(original(p))
    view.update(rows)
    return view


def clean(name):
    return {k: (TOMB if v[1] else v) for k, v in original(name).items()}


def visible(view):
    return {k: v for k, v in view.items() if v is not TOMB}


def evaluate(chosen, policy=POLICY):
    """(cost, live originals, views) when `chosen` is permitted and safe, else None."""
    if any(not policy[n][0] for n in chosen):
        return None
    live = set()

    def eff(name):
        if name in chosen:
            return clean(name)
        live.add(name); parents, rows = NODES[name]; view = {}
        for p in parents:
            view.update(eff(p))
        view.update(rows)
        return view
    views = {o: visible(eff(n)) for o, n in HEADS.items()}
    dirty = {n for n, (_, rows) in NODES.items() if any(e for _, e in rows.values())}
    if live & dirty or any(views[o] != visible(clean(n)) for o, n in HEADS.items()):
        return None
    return sum(policy[n][1] for n in chosen), live, views


def best(policy=POLICY):
    found = []
    for size in range(len(NODES) + 1):
        for combo in combinations(sorted(NODES), size):
            r = evaluate(set(combo), policy)
            if r:
                found.append((r[0], size, list(combo), r))
    found.sort(key=lambda f: f[:3])
    return found


if __name__ == '__main__':
    safe = best(); cost, _, chosen, (_, live, views) = safe[0]
    draft = dict(POLICY, S=(True, 1)); no_s = dict(POLICY, S=(False, 4))
    result = {'heads': HEADS, 'erased': ['B.x', 'U.unused'], 'safe_permitted_plans': len(safe),
              'chosen': chosen, 'cost': cost, 'runner_up': {'rewrites': safe[1][2], 'cost': safe[1][0]},
              'live_originals': sorted(live), 'purge_nodes': sorted(set(NODES) - live - HELD),
              'retained_for_hold': sorted(HELD),
              'views': {o: sorted(v[0] for v in vs.values()) for o, vs in views.items()},
              'if_unapproved_draft_used': {'rewrites': best(draft)[0][2], 'cost': best(draft)[0][0]},
              'if_S_denied': {'rewrites': best(no_s)[0][2], 'cost': best(no_s)[0][0]},
              'root_only_cost': evaluate({'R1', 'R2'})[0],
              'tombstone_needed': evaluate({'S'}) is not None and 'C.x' not in
              [v[0] for v in evaluate({'S'})[2]['orders'].values()]}
    Path(__file__).with_name('proof_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
