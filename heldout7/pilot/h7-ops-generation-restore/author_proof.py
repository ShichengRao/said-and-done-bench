"""Author-only independent current-evidence proof; no candidate imports."""
from collections import defaultdict
from itertools import combinations
import hashlib
import json
from pathlib import Path

def gf(a,b):
    bits=0
    for i in range(8):
        if b & (1<<i): bits ^= a<<i
    for i in range(14,7,-1):
        if bits & (1<<i): bits ^= 0x11b<<(i-8)
    return bits

def dot(coefficients, value):
    out=0
    for c,v in zip(coefficients,value): out ^= gf(c,v)
    return out

def rows(request):
    grouped=defaultdict(list)
    for row in request['fragments']:grouped[row['id']].append(row)
    answer=[]
    for delivered in grouped.values():
        by_revision=defaultdict(list)
        for row in delivered:by_revision[row['revision']].append(row)
        if any(any(r!=group[0] for r in group) for group in by_revision.values()):raise ValueError('conflict')
        row=by_revision[max(by_revision)][0]
        raw=json.dumps({k:row[k] for k in ('coefficients','value')},sort_keys=True,separators=(',',':')).encode()
        if row['live'] and (row['tenant'],row['generation'])==(request['tenant'],request['generation']) and hashlib.sha256(raw).hexdigest()==row['sha256']:
            answer.append(row)
    return answer

def canonical_proof(request):
    admitted=rows(request)
    # Three independent record IDs bind each of positions0/2 to the same value.
    # At most2 bad records leaves one sound equation from each triple.
    first=[r for r in admitted if r['coefficients'] in ([1,0,0,0],[2,0,0,0])]
    third=[r for r in admitted if r['coefficients'] in ([0,0,1,0],[0,0,2,0])]
    assert len(first)==len(third)==3 and request['fault_budget']==2
    assert all(dot(r['coefficients'],[10,0,30,0])==r['value'] for r in first+third)
    originals=[];mismatches={}
    for second in range(256):
        for fourth in range(256):
            value=bytes([10,second,30,fourth])
            bad=[r['id'] for r in admitted if dot(r['coefficients'],value)!=r['value']]
            if len(bad)<=2: originals.append(value.hex());mismatches[value.hex()]=sorted(bad)
    return {'selected_ids':sorted(r['id'] for r in admitted),'originals':originals,'mismatches':mismatches}

def rank(matrix):
    # Independent forward elimination, without copying the reference RREF solver.
    a=[list(row) for row in matrix];used=0
    for col in range(len(a[0]) if a else 0):
        pivot=next((i for i in range(used,len(a)) if a[i][col]),None)
        if pivot is None:continue
        a[used],a[pivot]=a[pivot],a[used]
        for i in range(used+1,len(a)):
            left,right=a[used][col],a[i][col]
            a[i]=[gf(left,x)^gf(right,y) for x,y in zip(a[i],a[used])]
        used+=1
    return used

def valid_profile(request):
    selected=rows(request)
    return (len(selected)<=14 and len(request['fragments'])<=40 and
            all(rank([r['coefficients'] for i,r in enumerate(selected) if i not in omitted])>=request['width']-1
                for count in range(min(request['fault_budget'],len(selected))+1)
                for omitted in combinations(range(len(selected)),count)))
