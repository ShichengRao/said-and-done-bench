from functools import lru_cache
from itertools import product
import random,json
N=4;M=6

def evaluate(allowed):
 @lru_cache(None)
 def solve(loc,done,bad,budget):
  if done==(1<<N)-1:return (True,True,(),())
  free=set(range(M))-set(loc)-({bad} if bad>=0 else set())
  legal=[];nominal=[];winning=[]
  for i in range(N):
   if done>>i&1:continue
   for j in allowed[i]:
    if j not in free:continue
    nxt=list(loc);nxt[i]=j;nxt=tuple(nxt)
    yes=solve(nxt,done|1<<i,bad,budget)
    no=solve(loc,done,j,0) if budget else None
    a=(i,j);legal.append(a)
    if yes[1]:nominal.append(a)
    if yes[0] and (not budget or no[0]):winning.append(a)
  return (bool(winning),bool(nominal),tuple(nominal),tuple(winning))
 initial=(tuple(range(N)),0,-1,1)
 result=solve(*initial)
 return result,solve,initial

if __name__=='__main__':
 random.seed(7301)
 for _ in range(20000):
  a=[tuple(sorted(random.sample([j for j in range(M) if j!=i],random.choice([2,3,4])))) for i in range(N)]
  res,solve,s=evaluate(a)
  if not res[0] or len(res[3])<1 or len(res[2])<4:continue
  # Several nominal first choices are genuinely losing, including lexical first;
  # successful winning first action must still leave a nontrivial choice later.
  if res[2][0] in res[3] or len(res[2])-len(res[3])<2:continue
  best=res[3][0];loc=list(s[0]);loc[best[0]]=best[1];nxt=(tuple(loc),1<<best[0],-1,1)
  r2=solve(*nxt)
  if len(r2[2])>=3 and 0<len(r2[3])<len(r2[2]):
   print(json.dumps({'allowed':a,'initial':res,'after_success':r2,'cache':str(solve.cache_info())}));break
