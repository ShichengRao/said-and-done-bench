from copy import deepcopy

def apply_batch(state,events):
    out=deepcopy(state)
    for e in events:
        key=e['merchant']+':'+e['id']
        if key in out['seen']:continue
        out['seen'][key]=e
        if e['kind']=='capture':
            out['captures'][key]={'cents':e['cents'],'refunded':0}
            out['balances'][e['merchant']]=out['balances'].get(e['merchant'],0)+e['cents']
    return out
