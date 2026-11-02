import json
from pathlib import Path
rows=json.loads(Path('data/journals.json').read_text());ticket=json.loads(Path('data/ticket.json').read_text())
latest={};seen={}
for r in rows:
    k=(r['journal_id'],r['revision'])
    if k in seen and seen[k]!=r:raise ValueError('conflicting replay')
    seen[k]=r
    if r['revision']>latest.get(r['journal_id'],{}).get('revision',0):latest[r['journal_id']]=r
revenue=0;contributing=[];excluded={}
for i,r in sorted(latest.items()):
    if sum(x['debit_cents'] for x in r['lines'])!=sum(x['credit_cents'] for x in r['lines']):raise ValueError('unbalanced journal')
    reason='canceled' if r['canceled'] else 'other_period' if r['effective_period']!=ticket['period'] else 'other_currency' if r['currency']!='USD' else None
    if reason:excluded[i]=reason;continue
    n=sum(x['credit_cents']-x['debit_cents'] for x in r['lines'] if x['account']=='4100')
    revenue+=n
    if n:contributing.append(i)
result=dict(period=ticket['period'],recognized_cents=revenue,target_cents=ticket['minimum_revenue_cents'],shortfall_cents=max(0,ticket['minimum_revenue_cents']-revenue),meets_target=revenue>=ticket['minimum_revenue_cents'],contributing_journals=contributing,excluded_journals=excluded)
Path('audit.json').write_text(json.dumps(result,indent=2)+'\n')
