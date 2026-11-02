from collections import deque

def plan(spec):
    nodes=sorted(spec['nodes'],key=lambda n:n['id']); ids=[n['id'] for n in nodes]
    initial=tuple(spec['initial'].get(i,'empty') for i in ids)
    def valid(state):
        ready=[n for n,v in zip(nodes,state) if v!='empty']
        return (spec['min_ready']<=len(ready)<=spec['max_total']
                and len({n['zone'] for n in ready})>=spec['min_zones'])
    def final(state):
        return (state.count('new')==spec['desired'] and 'old' not in state
                and all(v=='empty' for n,v in zip(nodes,state) if n['maintenance']))
    if not valid(initial): raise ValueError('invalid initial state')
    seen={initial}; queue=deque([(initial,[])])
    while queue:
        state,path=queue.popleft()
        if final(state): return path
        for op in ('start','stop'):
            for i,node in enumerate(nodes):
                if op=='start':
                    if state[i]!='empty' or not node['eligible'] or node['maintenance']: continue
                    value='new'
                else:
                    if state[i]=='empty': continue
                    value='empty'
                nxt=state[:i]+(value,)+state[i+1:]
                if nxt in seen or not valid(nxt): continue
                seen.add(nxt); queue.append((nxt,path+[{'op':op,'node':node['id']}]))
    return None
