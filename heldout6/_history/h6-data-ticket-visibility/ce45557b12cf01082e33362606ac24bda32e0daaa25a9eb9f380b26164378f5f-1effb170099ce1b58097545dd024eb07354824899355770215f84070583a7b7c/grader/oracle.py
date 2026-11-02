"""Independent replay oracle rebuilds every complete prefix snapshot from accepted messages."""
import copy,hashlib,json

def transform(b):
    messages=[];initial=copy.deepcopy(b['initial']);trace=[]
    def compute():
        fragments={};seals={};counts={}
        for m in messages:
            e=m['epoch'];n=m['parts']
            if e in counts and counts[e]!=n:raise ValueError('part count')
            counts[e]=n
            if m['kind']=='seal':
                if e in seals and seals[e]!=m:raise ValueError('seal')
                seals[e]=m
            else:
                key=(e,m['part'])
                if key in fragments and fragments[key]!=m:raise ValueError('fragment')
                fragments[key]=m
        for (e,k),m in fragments.items():
            if e in seals:
                actual=hashlib.sha256(json.dumps(m['operations'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
                if actual!=seals[e]['digests'][k]:raise ValueError('digest')
        snapshots={0:copy.deepcopy(initial)};published=0
        while published+1 in seals and all((published+1,k) in fragments for k in range(counts[published+1])):
            e=published+1;state=copy.deepcopy(initial)
            # Reconstruct from epoch zero, not from a mutating incremental state.
            for revision in range(1,e+1):
                for part in range(counts[revision]):
                    for op in fragments[revision,part]['operations']:
                        if op['kind']=='put_folder':state['folders'][op['id']]={'parent':op['parent'],'acl':copy.deepcopy(op['acl'])}
                        if op['kind']=='put_document':state['documents'][op['id']]={field:copy.deepcopy(op[field]) for field in ['folder','title','acl','deleted']}
                        if op['kind']=='delete_document' and op['id'] in state['documents']:state['documents'][op['id']]['deleted']=True
                        if op['kind']=='set_memberships':state['memberships'][op['user']]=list(op['groups'])
            for name in state['folders']:
                ancestry=[];cur=name
                while cur is not None:
                    if cur in ancestry or cur not in state['folders']:raise ValueError('graph')
                    ancestry.append(cur);cur=state['folders'][cur]['parent']
            if any(not d['deleted'] and d['folder'] not in state['folders'] for d in state['documents'].values()):raise ValueError('folder')
            snapshots[e]=state;published=e
        pending=[{'epoch':e,'parts':counts[e],'received':sorted(k for revision,k in fragments if revision==e),'sealed':e in seals} for e in sorted(counts) if e>published]
        return snapshots,{'published':published,'pending':pending}
    snapshots,status=compute()
    for command in b['trace']:
        if command['kind']=='ingest':messages.extend(copy.deepcopy(command['messages']));snapshots,status=compute();trace.append({'kind':'ingest',**status})
        else:
            e=command['epoch'];user=command['user']
            if e not in snapshots:raise ValueError('unpublished epoch')
            s=snapshots[e];groups=set(s['memberships'].get(user,[]));visible=[]
            for name in sorted(s['documents']):
                d=s['documents'][name]
                if d['deleted']:continue
                acl=d['acl'];ancestors=[];cur=d['folder']
                while cur is not None:ancestors.append(s['folders'][cur]);cur=s['folders'][cur]['parent']
                candidates=[acl]+[f['acl'] for f in ancestors]
                effective=next((a for a in candidates if a is not None),[])
                if any(g in groups for g in effective):visible.append({'id':name,'title':d['title'],'folder':d['folder']})
            trace.append({'kind':'query','epoch':e,'user':user,'visible':visible})
    ready=status['published']>=b['request']['minimum_epoch']
    return {'ready':ready,'trace':trace,**status,'blocker_codes':[] if ready else ['sealed_revision_evidence_required']}
