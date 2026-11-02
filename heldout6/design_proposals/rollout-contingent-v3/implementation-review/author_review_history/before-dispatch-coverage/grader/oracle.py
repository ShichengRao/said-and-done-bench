"""Independent literal order/route oracle. No recursive adversarial solver import."""
from functools import lru_cache
from itertools import permutations, product


def _inputs(rollouts, locations, done, bad, nodes, capacity):
    names=tuple(sorted(rollouts))
    return names,tuple(tuple(rollouts[s]['targets']) for s in names),tuple(locations[s] for s in names),tuple(s in done for s in names),tuple(sorted(bad)),tuple(nodes),capacity


@lru_cache(None)
def _schedules(names,routes,position,finished,bad,nodes,capacity):
    remaining=tuple(i for i,f in enumerate(finished) if not f)
    if not remaining:return ((),)
    if capacity<=len(names):return ()
    result=[]
    for order in permutations(remaining):
        for choices in product(*(routes[i] for i in order)):
            occupied=list(position);path=[]
            for i,target in zip(order,choices):
                if target in occupied or target in bad:break
                occupied[i]=target;path.append((names[i],target))
            else:result.append(tuple(path))
    return tuple(result)


def schedules(rollouts,locations,done,bad,nodes,capacity):
    return _schedules(*_inputs(rollouts,locations,done,bad,nodes,capacity))


def robust_spines(rollouts,locations,done,bad,nodes,capacity,budget):
    result=[]
    for path in schedules(rollouts,locations,done,bad,nodes,capacity):
        if budget==0:
            result.append(path);continue
        placed=dict(locations);finished=set(done)
        for service,target in path:
            if not schedules(rollouts,placed,finished,set(bad)|{target},nodes,capacity):break
            placed[service]=target;finished.add(service)
        else:result.append(path)
    return result


def winning(rollouts,locations,done,bad,nodes,capacity,budget):
    return bool(robust_spines(rollouts,locations,done,bad,nodes,capacity,budget))


def projections(snapshot,handoffs):
    tickets=snapshot['rollouts'];done=set(snapshot['done'])
    placements={s:t['source'] for s,t in tickets.items()}
    for node,value in snapshot['observed'].items():
        if value is not None and value['service'] in done:placements[value['service']]=node
    unknown=[s for s,h in handoffs.items() if h['phase']=='starting']
    for outcomes in product([True,False],repeat=len(unknown)):
        if outcomes.count(False)>snapshot['faults_left']:continue
        failed={s for s,ok in zip(unknown,outcomes) if not ok}
        loc=dict(placements);complete=set(done);bad=set(snapshot['quarantine'])
        for service,h in handoffs.items():
            if service in failed:bad.add(h['target'])
            else:loc[service]=h['target'];complete.add(service)
        yield loc,complete,bad,snapshot['faults_left']-len(failed)


def all_pending_outcomes_win(snapshot,handoffs,configuration):
    return all(winning(snapshot['rollouts'],loc,done,bad,configuration['nodes'],configuration['capacity'],left)
               for loc,done,bad,left in projections(snapshot,handoffs))
