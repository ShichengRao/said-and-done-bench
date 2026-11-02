from itertools import permutations,product
import json
routes=((2,3,4,5),(0,4),(3,5),(1,2,5));initial=(0,1,2,3)

def plans(loc,done=(),bad=()):
 left=tuple(i for i in range(4) if i not in done)
 out=[]
 for order in permutations(left):
  for destinations in product(*(routes[i] for i in order)):
   position=list(loc);ok=True;actions=[]
   for i,j in zip(order,destinations):
    if j in position or j in bad:ok=False;break
    position[i]=j;actions.append((i,j))
   if ok:out.append(tuple(actions))
 return out
nominal=plans(initial)
robust=[];first={};witness_failures={}
for p in nominal:
 loc=list(initial);done=[];recoveries=[]
 for i,j in p:
  recovery=plans(tuple(loc),tuple(done),(j,))
  recoveries.append(recovery)
  loc[i]=j;done.append(i)
 if all(recoveries):robust.append(p)
 first.setdefault(str(p[0]),{'nominal':0,'robust':0});first[str(p[0])]['nominal']+=1
 if all(recoveries):first[str(p[0])]['robust']+=1
p=((1,4),(2,5),(3,1),(0,2));loc=list(initial);done=[]
for i,j in p:
 recovery=plans(tuple(loc),tuple(done),(j,));witness_failures[str((i,j))]={'recoveries':len(recovery),'one':recovery[0]}
 loc[i]=j;done.append(i)
res={'routes':routes,'initial':initial,'nominal_plans':len(nominal),'robust_nominal_spines':len(robust),'first_actions':first,
 'initial_quarantine_relaxations':{str(j):len(plans(initial,bad=(j,))) for j in [4,5]},
 'chosen_nominal':p,'recovery_branches':witness_failures,
 'greedy_plan':nominal[0],'greedy_counterexample':'A→4 succeeds, then B→0 fails: B has no free authorized target (0 quarantined;4 occupied by A).'}
print(json.dumps(res,indent=2));open('/tmp/rollout_contingent_literal_proof.json','w').write(json.dumps(res,indent=2)+'\n')
