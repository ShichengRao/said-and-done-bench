import copy,random

def empty():
 return {'schedule':{'as_of':0,'slots':[0],'workers':{'0':0},'budgets':{'root':0},'credentials':[],'requests':[],'routes':[]},'ledger':{'attempts':[],'receipts':[]},'proposals':[]}

def small(seed):
 rng=random.Random(seed);n=1+seed%3
 c=[dict(id='root',parent=None,scopes=['run'],start=0,end=5,pool='root'),dict(id='leaf',parent='root',scopes=['run'],start=0,end=3+seed%2,pool='leaf')]
 q=[dict(id='q'+str(i),scopes=['run'],units=rng.randint(1,3),duration=1,earliest=1,latest=3+seed%2,leaves=['leaf']) for i in range(n)]
 a=[dict(id='old',key='old',at=0,credentials=['root','leaf'],units=1,transport='timeout')]
 r=[dict(id='ack',kind='reserve',at=0,reservation='old-res',attempt='old',expires=1+seed%3)]
 if seed%4==0:r.append(dict(id='commit',kind='commit',at=0,reservation='old-res'))
 if seed%4==1:r.append(dict(id='release',kind='release',at=1,reservation='old-res'))
 return {'schedule':dict(as_of=1,slots=[1,2,3],workers={str(t):rng.randint(2,5) for t in [1,2,3]},budgets={'root':10,'leaf':rng.randint(2,8)},credentials=c,requests=q,routes=[dict(id='route'+str(i),request=x['id'],credentials=['root','leaf']) for i,x in enumerate(q)]),'ledger':dict(attempts=a,receipts=r),'proposals':[dict(id='more',kind='budget',pool='leaf',units=2,cost=1)]}

def cases(source):
 for seed in range(12):yield 'generated-'+str(seed),small(seed)
 b=small(1)
 for q in b['schedule']['requests']:q['latest']=2
 yield 'tight-deadline-with-live-credentials',b
 b=small(1);b['schedule']['credentials'][1]['end']=2
 yield 'tight-credential-with-later-deadline',b
 yield 'empty',empty()
 for prop in source['proposals']:
  b=copy.deepcopy(source);s=b['schedule']
  if prop['kind']=='budget':s['budgets'][prop['pool']]+=prop['units']
  else:s['workers'][str(prop['slot'])]+=prop['units']
  yield 'actual-'+prop['id'],b
 b=copy.deepcopy(source)
 for key in ('attempts','receipts'):b['ledger'][key].reverse()
 for key in ('credentials','requests','routes','slots'):b['schedule'][key].reverse()
 b['proposals'].reverse();yield 'unordered-records',b
 b=copy.deepcopy(source);b['ledger']['attempts']+=copy.deepcopy(b['ledger']['attempts'][:2]);b['ledger']['receipts']+=copy.deepcopy(b['ledger']['receipts'][:3]);yield 'identical-replays',b
 b=copy.deepcopy(source);b['ledger']['receipts'].append(dict(id='late-commit-replay',kind='commit',at=9,reservation='spent-C'));yield 'committed-replay-after-expiry',b
 b=copy.deepcopy(source);b['ledger']['receipts'].append(dict(id='future-release',kind='release',at=10,reservation='held-C-late'));yield 'invisible-future-release',b
 b=copy.deepcopy(source);b['ledger']['receipts'].append(dict(id='visible-release',kind='release',at=9,reservation='held-C-late'));yield 'release-at-cutoff',b
 b=copy.deepcopy(source)
 for a in b['ledger']['attempts']:
  if a['id']=='rejected-replacement':a['credentials']=['root','replacement-route'];a['units']=2
 yield 'rejected-retry-does-not-rebind',b
 b=copy.deepcopy(source);b['schedule']['as_of']=12;b['schedule']['slots']=[12];b['schedule']['workers']={k:v for k,v in b['schedule']['workers'].items() if k=='12'};b['proposals']=[p for p in b['proposals'] if p['kind']=='budget' or p['slot']==12];yield 'expiry-at-cutoff',b
 b=copy.deepcopy(source);s=b['schedule'];delta=17;s['as_of']+=delta;s['slots']=[x+delta for x in s['slots']];s['workers']={str(int(k)+delta):v for k,v in s['workers'].items()}
 for c in s['credentials']:c['start']+=delta;c['end']+=delta
 for q in s['requests']:q['earliest']+=delta;q['latest']+=delta
 for a in b['ledger']['attempts']:a['at']+=delta
 for r in b['ledger']['receipts']:
  r['at']+=delta
  if 'expires' in r:r['expires']+=delta
 for p in b['proposals']:
  if p['kind']=='worker':p['slot']+=delta
 yield 'time-origin-shift',b
 b=copy.deepcopy(source);b['ledger']['attempts'].append({**b['ledger']['attempts'][0],'units':99});yield 'invalid-conflicting-attempt-replay',b
 b=copy.deepcopy(source);b['ledger']['receipts'].append({**b['ledger']['receipts'][0],'expires':99});yield 'invalid-conflicting-receipt-replay',b
 b=copy.deepcopy(source);b['ledger']['receipts'].append(dict(id='conflicting-binding',kind='reserve',at=8,reservation='held-C-late',attempt='retry-C-timeout',expires=12));yield 'invalid-reservation-rebinding',b
 b=copy.deepcopy(source);b['ledger']['receipts'].append(dict(id='key-collision',kind='reserve',at=8,reservation='other',attempt='hold-C-late',expires=12));yield 'invalid-key-collision',b
 b=copy.deepcopy(source);b['ledger']['receipts'].append(dict(id='contradictory-release',kind='release',at=8,reservation='spent-C'));yield 'invalid-conflicting-terminals',b
 b=copy.deepcopy(source);b['ledger']['receipts'].append(dict(id='early-commit',kind='commit',at=0,reservation='held-C-late'));yield 'invalid-terminal-before-reserve',b
 b=copy.deepcopy(source);b['ledger']['receipts'].append(dict(id='at-expiry-commit',kind='commit',at=8,reservation='expired'));yield 'invalid-commit-at-expiry',b
 b=copy.deepcopy(source);b['ledger']['receipts'][0]['attempt']='ghost';yield 'invalid-unknown-attempt',b
 b=copy.deepcopy(source);b['schedule']['routes'][0]['credentials'].append('ghost');yield 'invalid-unknown-route-credential',b
 b=copy.deepcopy(source);b['schedule']['credentials'].append(copy.deepcopy(b['schedule']['credentials'][0]));yield 'invalid-duplicate-credential',b

def independent_checks(transform,source):
 r=transform(copy.deepcopy(source));assert not r['ready'] and r['assignment'] is None
 assert r['availability']['A']=={'10':3,'11':6,'12':9}
 assert r['availability']['B']=={'10':3,'11':3,'12':5}
 assert r['availability']['C']=={'10':3,'11':3,'12':6}
 assert r['availability']['D']=={'10':3,'11':5,'12':6}
 assert r['reservation_state']['spent-C']['state']=='committed'
 assert r['reservation_state']['spent-C']['attempt']=='accepted-C'
 assert r['reservation_state']['held-C-late']['state']=='held'
 assert r['obstruction']==['request-'+str(i) for i in range(6)]
 assert r['owner_request']['proposal_ids']==['allowance-C'] and r['owner_request']['cost']==2
 b=copy.deepcopy(source);b['schedule']['budgets']['C']+=1
 assert transform(b)['ready'] and transform(b)['owner_request']['proposal_ids']==[]
 for name in ['request-'+str(i) for i in range(6)]:
  b=copy.deepcopy(source);b['schedule']['requests']=[q for q in b['schedule']['requests'] if q['id']!=name];b['schedule']['routes']=[r for r in b['schedule']['routes'] if r['request']!=name]
  assert transform(b)['ready']

def cli_success_cases():return [('empty',empty()),('small',small(3))]
