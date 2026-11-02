"""Trusted financial checks and independent half-join; never imports candidate code."""
import json
from collections import defaultdict
from itertools import product
from pathlib import Path


def read_batch(root):
    root = Path(root)
    def read(name): return json.loads((root/name).read_text())
    return dict(period=read('period.json'), deliveries=[json.loads(s) for s in (root/'processor.jsonl').read_text().splitlines() if s.strip()],
                journal=read('posted_journal.json'), controls=read('signed_close_controls.json'), bank=read('bank_settlement.json'))


def write_batch(root, batch):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    for name,key in [('period.json','period'),('posted_journal.json','journal'),('signed_close_controls.json','controls'),('bank_settlement.json','bank')]:
        (root/name).write_text(json.dumps(batch[key], indent=2)+'\n')
    (root/'processor.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in batch['deliveries']))


def facts(batch):
    groups = defaultdict(lambda: defaultdict(list))
    for event in batch['deliveries']:
        if event['known'] <= batch['period']['as_of']:
            groups[event['kind'],event['id']][event['revision']].append({k:v for k,v in event.items() if k!='event_id'})
    selected = {}
    for key,revisions in groups.items():
        for copies in revisions.values():
            if any(row != copies[0] for row in copies): raise ValueError('conflicting processor revision')
        eligible = [rows[0] for rows in revisions.values() if rows[0]['final']]
        if eligible: selected[key] = sorted(eligible,key=lambda row:row['revision'])[-1]
    captures = {identity:row for (kind,identity),row in selected.items() if kind=='capture'}
    refunds = {identity:0 for identity in captures}
    for (kind,identity),row in selected.items():
        if kind=='refund': refunds[row['capture']] += row['amount_cents']
    fixed = {row['capture']:row['merchant'] for row in batch['journal'] if row['signed'] and row['closed']}
    return captures,refunds,fixed


def solutions(batch):
    """Join independent receipt-half totals; return count and one complete attribution."""
    captures,refunds,fixed = facts(batch)
    controls = [(merchant,key,value) for merchant,row in sorted(batch['controls'].items()) for key,value in sorted(row.items())]
    def contribution(mapping):
        return tuple(sum((captures[i]['amount_cents'] if key=='gross_cents' else refunds[i]) for i,m in mapping.items() if m==merchant)
                     for merchant,key,wanted in controls)
    gross=sum(r['amount_cents'] for r in captures.values()); refunded=sum(refunds.values())
    if batch['bank'] != dict(gross_cents=gross,refund_cents=refunded,net_cents=gross-refunded): return 0,None
    remaining=sorted(set(captures)-set(fixed));left,right=remaining[:len(remaining)//2],remaining[len(remaining)//2:]
    def choices(identities):
        for values in product(*(captures[i]['eligible'] for i in identities)):
            yield dict(zip(identities,values))
    index={}
    for mapping in choices(right):
        key=contribution(mapping);count,old=index.get(key,(0,None));index[key]=(count+1,mapping if old is None else old)
    base=contribution(fixed);count=0;witness=None
    for mapping in choices(left):
        partial=contribution(mapping);needed=tuple(c[2]-a-b for c,a,b in zip(controls,base,partial))
        n,other=index.get(needed,(0,None));count+=n
        if n and witness is None:witness={**fixed,**mapping,**other}
    return count,witness


def validate_close(package,batch):
    errors=[];captures,refunds,fixed=facts(batch);period=batch['period']
    if not isinstance(package,dict):return ['close is not an object']
    for key in ('batch','currency','as_of'):
        if package.get(key)!=period[key]:errors.append('incorrect '+key)
    lines=package.get('allocations')
    if not isinstance(lines,list):return errors+['missing supporting capture lines']
    identities=[r.get('capture') if isinstance(r,dict) else None for r in lines]
    if len(identities)!=len(set(identities)) or set(identities)!=set(captures):
        return errors+['supporting lines must contain every current capture exactly once']
    merchant_totals={m:dict(gross_cents=0,refund_cents=0,net_cents=0,capture_count=0) for m in period['merchants']}
    for row in lines:
        identity=row['capture'];merchant=row.get('merchant')
        if merchant not in captures[identity]['eligible'] or merchant not in merchant_totals:
            errors.append('unapproved merchant for '+identity);continue
        if identity in fixed and merchant!=fixed[identity]:errors.append('changed closed posting for '+identity)
        expected=dict(gross_cents=captures[identity]['amount_cents'],refund_cents=refunds[identity],net_cents=captures[identity]['amount_cents']-refunds[identity])
        for key,amount in expected.items():
            if type(row.get(key)) is not int or row[key]!=amount:errors.append('incorrect '+key+' for '+identity)
            merchant_totals[merchant][key]+=amount
        merchant_totals[merchant]['capture_count']+=1
    actual=package.get('merchants')
    if not isinstance(actual,dict) or set(actual)!=set(merchant_totals):errors.append('merchant coverage differs')
    else:
        for merchant,expected in merchant_totals.items():
            row=actual[merchant]
            if not isinstance(row,dict) or any(type(row.get(k)) is not int or row[k]!=v for k,v in expected.items()):errors.append('incorrect merchant rollup '+merchant)
    for merchant,control in batch['controls'].items():
        if any(merchant_totals[merchant][key]!=amount for key,amount in control.items()):errors.append('signed control differs for '+merchant)
    expected={key:sum(t[key] for t in merchant_totals.values()) for key in ['gross_cents','refund_cents','net_cents']}
    total=package.get('totals')
    if not isinstance(total,dict) or any(type(total.get(k)) is not int or total[k]!=v for k,v in expected.items()):errors.append('account rollup differs')
    if expected!=batch['bank']:errors.append('bank settlement differs')
    return sorted(set(errors))
