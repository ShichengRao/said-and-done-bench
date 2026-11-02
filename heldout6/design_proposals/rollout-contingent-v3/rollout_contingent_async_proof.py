from itertools import combinations,product
from rollout_contingent_design import evaluate
from rollout_contingent_literal_proof import plans
import json
routes=((2,3,4,5),(0,4),(3,5),(1,2,5));initial=(0,1,2,3)
_,solve,_=evaluate(routes)
initial_starts=[(i,j) for i in range(4) for j in routes[i] if j not in initial]
rows=[]
for pair in combinations(initial_starts,2):
 if len({i for i,j in pair})<2 or len({j for i,j in pair})<2:continue
 outcomes=[]
 for successes in [(True,True),(False,True),(True,False)]:
  loc=list(initial);done=0;bad=-1
  for (i,j),ok in zip(pair,successes):
   if ok:loc[i]=j;done|=1<<i
   else:bad=j
  state=(tuple(loc),done,bad,1 if all(successes) else 0)
  result=solve(*state)
  outcomes.append({'successes':successes,'macro_locations':loc,'quarantine':bad,'faults_left':state[3],
    'winning':result[0],'winning_next':result[3],
    'ordinary_completion_count':len(plans(tuple(loc),tuple(i for i in range(4) if done>>i&1),() if bad<0 else (bad,)))})
 rows.append({'starts':pair,'winning_for_every_outcome':all(o['winning'] for o in outcomes),'outcomes':outcomes})
# Explicit ACK distinction after C failure and before retiring B.
# Inventory counts BOTH old and known-ready new replicas until retirement ACK.
def ready_to_start(occupied,reserved,quarantined,finished,handoffs):
 return [(i,j) for i in range(4) if i not in finished and i not in handoffs
         for j in routes[i] if j not in occupied and j not in reserved and j not in quarantined
         and len(occupied)+len(reserved)+1<=6]
checks={
 'C_failed_B_start_pending':ready_to_start({0,1,2,3},{4},{5},set(),{1}),
 'C_failed_B_ready_before_retirement_ACK':ready_to_start({0,1,2,3,4},set(),{5},set(),{1}),
 'after_B_retirement_ACK':ready_to_start({0,2,3,4},set(),{5},{1},set()),
}
result={'initial_legal_pairs':rows,'actual_eligibility':checks,'macro_count_note':'44 nominal and10 robust-spine counts describe serialized completed cutovers, not counts of asynchronous receipt schedules.'}
open('/tmp/rollout_contingent_async_proof.json','w').write(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
