"""Valid generated instances and evidence-preserving counterfactuals."""
import copy,itertools,random

def approved(source,ids):
 d=copy.deepcopy(source);selected=[q for q in d['owner_requests'] if q['id'] in ids]
 for q in selected:
  for i,(a,b) in enumerate(q['edges']):d['links'].append(dict(id='actual-'+q['id']+'-'+str(i),revision=1,source=a,target=b,enabled=True,valid_from=d['at'],valid_to=d['at']+1))
 d['owner_requests']=[q for q in d['owner_requests'] if q['id'] not in ids]
 return d

def alternate_cases(base):
 d=copy.deepcopy(base);d['links'].reverse();yield 'reversed-grant-deliveries',d
 d=copy.deepcopy(base);d['links'].append(copy.deepcopy(d['links'][0]));yield 'identical-delivery',d
 d=copy.deepcopy(base);d['at']+=30
 for r in d['links']:r['valid_from']+=30;r['valid_to']+=30
 yield 'shift-export-time',d
 d=copy.deepcopy(base)
 for u in d['units']:d['initial']['images'][u]='new'
 yield 'already-new-images',d
 d=copy.deepcopy(base);d['rack_capacity']['r2']=6;yield 'actual-rack-expansion',d
 d=copy.deepcopy(base)
 for u in d['units']:d['units'][u]['size']=1
 yield 'small-physical-objects',d
 d=copy.deepcopy(base)
 for g in d['groups']:d['groups'][g]['min_zones']=1
 yield 'legitimate-single-zone-policy',d
 for q in base['owner_requests']:yield 'approved-'+q['id'],approved(base,{q['id']})
 yield 'both-cheap-grants',approved(base,{'direct-heavy-15','east-return-52'})
 d=approved(base,{'approve-relay-03'})
 for u in d['units']:d['units'][u]['allowed_final']=[d['target'][u]]
 yield 'staging-outside-only-final-node',d
 d=copy.deepcopy(base);d['links']=[r for r in d['links'] if not(r['id']=='regional-relay' and r['revision']==2)];yield 'older-authorized-snapshot',d
 d=copy.deepcopy(base);d['at']=11;yield 'future-grant-is-now-active',d
 d=copy.deepcopy(base);d['at']=20;yield 'exact-expiry-endpoint',d
 d=copy.deepcopy(base);d['owner_requests']=[];yield 'no-owner-options',d
 d=approved(base,{'approve-relay-03'});d['units']['u0']['allowed_final']=[];yield 'no-approved-final-destination',d
 # Renaming preserves IDs' referential structure; recompute tie-breaks under new lexical names.
 d=copy.deepcopy(base);nm={n:'host-'+str(5-int(n[1:])) for n in d['nodes']};um={u:'copy-'+str(4-int(u[1:])) for u in d['units']}
 d['nodes']={nm[n]:v for n,v in d['nodes'].items()}
 d['units']={um[u]:{**v,'allowed_final':[nm[n] for n in v['allowed_final']]} for u,v in d['units'].items()}
 d['initial']={'positions':{um[u]:nm[n] for u,n in d['initial']['positions'].items()},'images':{um[u]:im for u,im in d['initial']['images'].items()}};d['target']={um[u]:nm[n] for u,n in d['target'].items()}
 for row in d['links']:row['source']=nm[row['source']];row['target']=nm[row['target']]
 for q in d['owner_requests']:q['edges']=[[nm[a],nm[b]] for a,b in q['edges']]
 yield 'referential-renaming',d
 # Small complete and blocked models, including multiple empty destinations and simultaneous final choices.
 rng=random.Random(19433)
 for ix in range(12):
  n=3+ix%2;u=2+ix%2;sz=[rng.randint(1,3) for _ in range(u)];racks={f'n{i}':f'r{i//2}' for i in range(n)}
  caps={r:sum(sz[j] for j in range(u) if racks[f'n{j}']==r)+rng.randint(0,3) for r in set(racks.values())}
  # Every rack must fit a target singleton, but the signed target may still fail jointly.
  caps={r:max(max(sz),cap) for r,cap in caps.items()}
  target_nodes=list(range(n));rng.shuffle(target_nodes)
  d={'at':4,'nodes':{f'n{i}':dict(rack=racks[f'n{i}'],zone=str(i),capacity=3) for i in range(n)},'rack_capacity':caps,'groups':{'g':dict(quorum=u,min_zones=1+ix%2)},'units':{f'u{i}':dict(group='g',size=sz[i],allowed_final=[f'n{target_nodes[i]}']) for i in range(u)},'initial':{'positions':{f'u{i}':f'n{i}' for i in range(u)},'images':{f'u{i}':('new' if (i+ix)%3==0 else 'old') for i in range(u)}},'target':{f'u{i}':f'n{target_nodes[i]}' for i in range(u)},'links':[],'owner_requests':[]}
  for a,b in itertools.permutations(range(n),2):
   if rng.random()<.6:d['links'].append(dict(id=f'l{a}{b}',revision=1,source=f'n{a}',target=f'n{b}',enabled=True,valid_from=0,valid_to=5))
  d['owner_requests']=[dict(id='direct-owner',edges=[['n0',f'n{n-1}']],cost=1)]
  yield 'generated-'+str(ix),d
 yield 'empty-cluster',dict(at=0,nodes={},rack_capacity={},units={},groups={},initial=dict(positions={},images={}),target={},links=[],owner_requests=[])
