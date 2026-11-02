from copy import deepcopy

def apply_batch(state, events):
    out=deepcopy(state)
    new={}
    for e in events:
        if not isinstance(e,dict) or set(e)!={'merchant','id','sequence','kind','reference','cents'}: raise ValueError('shape')
        if any(not isinstance(e[k],str) or not e[k] or ':' in e[k] for k in ('merchant','id')): raise ValueError('identity')
        if type(e['sequence']) is not int or e['sequence']<=0 or type(e['cents']) is not int or e['cents']<=0: raise ValueError('number')
        if e['kind'] not in ('capture','refund','reverse'): raise ValueError('kind')
        if e['kind']=='capture':
            if e['reference'] is not None: raise ValueError('capture reference')
        elif not isinstance(e['reference'],str) or not e['reference'] or ':' in e['reference']: raise ValueError('reference')
        key=e['merchant']+':'+e['id']
        prior=out['seen'].get(key,new.get(key))
        if prior is not None:
            if prior != e: raise ValueError('conflicting replay')
        else:new[key]=deepcopy(e)
    last={}
    for e in out['seen'].values():last[e['merchant']]=max(last.get(e['merchant'],0),e['sequence'])
    for key,e in new.items():
        m=e['merchant']; n=e['cents']; k=e['kind']
        if e['sequence']<=last.get(m,0): raise ValueError('sequence')
        last[m]=e['sequence']
        if k=='capture':
            out['captures'][key]={'cents':n,'refunded':0}
            delta=n
        elif k=='refund':
            target=m+':'+e['reference']; c=out['captures'].get(target)
            if c is None or c['refunded']+n>c['cents']: raise ValueError('capture capacity')
            c['refunded']+=n
            out['refunds'][key]={'capture':target,'cents':n,'reversed':False}
            delta=-n
        else:
            target=m+':'+e['reference'];r=out['refunds'].get(target)
            if r is None or r['reversed'] or r['cents']!=n: raise ValueError('refund reversal')
            r['reversed']=True;out['captures'][r['capture']]['refunded']-=n
            delta=n
        out['balances'][m]=out['balances'].get(m,0)+delta
        out['seen'][key]=e
    return out
