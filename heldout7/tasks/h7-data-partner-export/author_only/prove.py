"""Author-only proof for h7-data-partner-export, independent of grader/oracle.py and workspace code.

Hand table from data/ (bit i = person p<i>): old releases p0..p3 count 1 (mask 15) and p4
count 0 (mask 16); current release p0..p3 count 2; max_changes 1; protected p0,p1,p2 (mask 7).
Consent: p0 rev1 allows (rev0 denial superseded); everyone consents. Packages after alias
resolution (export-p1 -> legacy-p1 -> p1): high mask 19 utility 5, medium mask 7 utility 4,
cross mask 5 utility 3. Actual snapshots: old 1, current 3.
"""
import json
from itertools import product
from pathlib import Path

PACKAGES = {'cross': (5, 3), 'high': (19, 5), 'medium': (7, 4)}  # id: (mask, utility)
PROTECTED = 7
ACTUAL_CURRENT = 3


def worlds(drop_old=False, bound=1):
    old = [v for v in range(32) if drop_old or ((v & 15).bit_count() == 1 and v & 16 == 0)]
    return sorted({c for c in range(32) for o in old if (c & 15).bit_count() == 2 and (c ^ o).bit_count() <= bound})


def safe(group):
    return all({w >> i & 1 for w in group} == {0, 1} for i in range(5) if PROTECTED >> i & 1)


def policies(ws, floor=3):
    names = sorted(n for n, (_, u) in PACKAGES.items() if u >= floor)
    found = []
    for table in product(names, repeat=len(ws)):
        groups = {}
        for w, n in zip(ws, table):
            groups.setdefault((n, (w & PACKAGES[n][0]).bit_count()), []).append(w)
        if all(safe(g) for g in groups.values()):
            found.append((sum(PACKAGES[n][1] for n in table), table))
    return found


def lexbest(ws, floor=3):
    found = policies(ws, floor)
    if not found:
        return None
    top = max(f[0] for f in found)
    return min(f[1] for f in found if f[0] == top), top, len(found)


if __name__ == '__main__':
    ws = worlds()
    table, total, count = lexbest(ws)
    i = ws.index(ACTUAL_CURRENT); pkg = table[i]; value = (ACTUAL_CURRENT & PACKAGES[pkg][0]).bit_count()
    fiber = [w for w, n in zip(ws, table) if n == pkg and (w & PACKAGES[n][0]).bit_count() == value]
    local = []  # per-world selector against full-baseline count groups
    for w in ws:
        ok = [n for n in PACKAGES if safe([x for x in ws if (x & PACKAGES[n][0]).bit_count() == (w & PACKAGES[n][0]).bit_count()])]
        local.append(max(ok, key=lambda n: (PACKAGES[n][1], [-ord(c) for c in n])))
    local_fiber = [w for w, n in zip(ws, local) if n == local[i] and (w & PACKAGES[n][0]).bit_count() == (ACTUAL_CURRENT & PACKAGES[local[i]][0]).bit_count()]
    floor4 = lexbest(ws, 4); floor5 = lexbest(ws, 5)
    dropped = worlds(drop_old=True); dt, dtot, _ = lexbest(dropped)
    result = {'worlds': ws, 'tables_checked': 3 ** len(ws), 'safe_policies': count,
              'policy': dict(zip(map(str, ws), table)), 'total_utility': total,
              'guaranteed_utility': min(PACKAGES[n][1] for n in table),
              'publication': {'package': pkg, 'count': value, 'utility': PACKAGES[pkg][1]}, 'candidate_fiber': fiber,
              'starter_local_policy': local, 'starter_local_fiber': local_fiber,
              'floor4': {'policy': list(floor4[0]), 'total': floor4[1]}, 'floor5': floor5,
              'drop_old': {'worlds': len(dropped), 'total': dtot, 'publication': dt[dropped.index(ACTUAL_CURRENT)]}}
    Path(__file__).with_name('proof_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
