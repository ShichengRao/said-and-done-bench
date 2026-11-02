import copy,hashlib,json,tempfile,subprocess,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def fragment(epoch,part,parts,ops):return {'kind':'fragment','epoch':epoch,'part':part,'parts':parts,'operations':ops}
def seal(fs):return {'kind':'seal','epoch':fs[0]['epoch'],'parts':len(fs),'digests':[hashlib.sha256(json.dumps(f['operations'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest() for f in fs]}
def ing(*m):return {'kind':'ingest','messages':list(m)}
def small(seed):
    initial={'folders':{'root':{'parent':None,'acl':['g']},'child':{'parent':'root','acl':None}},'documents':{'d':{'folder':'child','title':'old','acl':None,'deleted':False}},'memberships':{'u':['g']}}
    f=[fragment(1,0,2,[{'kind':'put_folder','id':'child','parent':'root','acl':[] if seed%2 else ['h']}]),fragment(1,1,2,[{'kind':'set_memberships','user':'u','groups':['h']},{'kind':'put_document','id':'d','folder':'child','title':'new','acl':None,'deleted':False}])]
    messages=[f[0],f[1],seal(f)];messages=messages[seed%3:]+messages[:seed%3]
    trace=[{'kind':'query','epoch':0,'user':'u'}]+[ing(m) for m in messages]+[{'kind':'query','epoch':1,'user':'u'},{'kind':'query','epoch':0,'user':'u'},ing(messages[0])]
    return {'initial':initial,'request':{'minimum_epoch':1},'trace':trace}

def cases(source):
    for n in range(6):yield f'generated-{n}',small(n)
    b=copy.deepcopy(source);b['request']['minimum_epoch']=4;yield 'minimum-not-yet-sealed',b
    b=small(0);b['trace'].append({'kind':'query','epoch':2,'user':'u'});yield 'query-unpublished',b
    b=small(0);m=copy.deepcopy(b['trace'][1]['messages'][0]);m['operations'][0]['acl']=['wrong'];b['trace'].append(ing(m));yield 'conflicting-history-replay',b
    b=small(0);m=copy.deepcopy(b['trace'][3]['messages'][0]);m['digests'][0]='0'*64;b['trace'].append(ing(m));yield 'conflicting-seal',b
    b=small(0);b['trace'][1]['messages'][0]['operations'][0]['parent']='child';fs=[b['trace'][1]['messages'][0],b['trace'][2]['messages'][0]];b['trace'][3]=ing(seal(fs));yield 'invalid-final-folder-cycle',b
    b=small(0);b['trace'][3]['messages'][0]['digests'][0]='f'*64;yield 'digest-mismatch',b

def independent_checks(transform,source,projection=None,module_dir=None):
    result=transform(copy.deepcopy(source))
    assert result['ready'] and result['published']==3 and result['pending']==[{'epoch':4,'parts':2,'received':[0],'sealed':False}]
    answers=[x for x in result['trace'] if x['kind']=='query']
    assert answers[0]['visible']==[{'id':'d1','title':'Basic','folder':'root'}]
    assert next(x for x in answers if x['epoch']==2 and x['user']=='amy')['visible']==[]
    assert next(x for x in answers if x['epoch']==3 and x['user']=='cy')['visible']==[{'id':'d1','title':'Current','folder':'customer'},{'id':'d2','title':'Audit copy','folder':'customer'}]
    import importlib.util
    helper=Path(__file__).resolve().with_name('projection_api.py')
    spec=importlib.util.spec_from_file_location('_trusted_ticket_api',helper);api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
    root=Path(module_dir or Path.cwd()).resolve()
    if projection is not None:
        check_projection(projection,source,result,root,api.child_bootstrap(root,{'path':'pipeline.py'}))
        return
    inventory=api.module_inventory(root)
    failures=[]
    for target,candidate in api.candidates(root,inventory):
        try:check_projection(candidate,source,result,root,api.child_bootstrap(root,target))
        except (Exception,SystemExit) as error:failures.append((target['path'],type(error).__name__,str(error)))
        else:return
    raise AssertionError(('no candidate Projection export passes the durable API contract',failures))


def check_projection(projection,source,result,module_dir,bootstrap):
    check_atomic_batches(projection)
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'nested'/'state.sqlite';store=projection(path,source['initial'])
        # Replay across fresh objects, checking both old and newly published views.
        for command,expected in zip(source['trace'],result['trace']):
            store=projection(path)
            if command['kind']=='ingest':assert store.ingest(copy.deepcopy(command['messages']))=={k:expected[k] for k in ['published','pending']}
            else:assert store.query(command['epoch'],command['user'])==expected['visible']
        before=store.status();old=store.query(0,'amy')
        conflict=copy.deepcopy(source['trace'][3]['messages'][0]);conflict['operations'][0]['title']='forged'
        new=fragment(5,0,1,[])
        try:store.ingest([new,conflict])
        except ValueError:pass
        else:raise AssertionError('batch conflict not rejected')
        assert projection(path).status()==before and projection(path).query(0,'amy')==old
        # Independent process must reopen durable pending/history evidence.
        code=bootstrap+"import json,sys;p=Projection(sys.argv[1]);print(json.dumps({'status':p.status(),'old':p.query(0,'amy')}))"
        run=subprocess.run([sys.executable,'-c',code,str(path)],cwd=module_dir or Path.cwd(),capture_output=True,text=True,timeout=20)
        assert run.returncode==0,run.stderr
        assert json.loads(run.stdout)=={'status':before,'old':old}
        try:projection(path,{**source['initial'],'memberships':{}})
        except ValueError:pass
        else:raise AssertionError('changed initial accepted')
        assert projection(path).status()==before
    # Two ingesters publish all parts once without overwriting each other's writes.
    with tempfile.TemporaryDirectory() as folder:
        b=small(0);path=Path(folder)/'concurrent.sqlite';projection(path,b['initial']);a=projection(path);c=projection(path)
        f0=b['trace'][1]['messages'][0];f1=b['trace'][2]['messages'][0];s=b['trace'][3]['messages'][0]
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures=[workers.submit(a.ingest,[f0,s]),workers.submit(c.ingest,[f1])]
            for future in futures:future.result()
        assert projection(path).status()=={'published':1,'pending':[]}
        assert projection(path).query(0,'u')==[{'id':'d','title':'old','folder':'child'}]

    # Synchronized separate processes must merge complementary fragments/seal.
    with tempfile.TemporaryDirectory() as folder:
        import time
        root=Path(folder);path=root/'process.sqlite';b=small(0);projection(path,b['initial'])
        batches=[[b['trace'][1]['messages'][0],b['trace'][3]['messages'][0]],[b['trace'][2]['messages'][0]]]
        gate=root/'go';children=[]
        code=bootstrap+"""from pathlib import Path
import json,sys,time
store=Projection(sys.argv[1]);payload=json.loads(Path(sys.argv[2]).read_text());Path(sys.argv[3]).write_text('ready')
deadline=time.monotonic()+15
while not Path(sys.argv[4]).exists():
    if time.monotonic()>deadline:raise RuntimeError('gate timeout')
    time.sleep(.01)
print(json.dumps(store.ingest(payload)))
"""
        for i,batch in enumerate(batches):
            source=root/f'batch{i}.json';source.write_text(json.dumps(batch));ready=root/f'ready{i}'
            children.append(subprocess.Popen([sys.executable,'-c',code,str(path),str(source),str(ready),str(gate)],cwd=module_dir or Path.cwd(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
        try:
            deadline=time.monotonic()+15
            while not all((root/f'ready{i}').exists() for i in range(2)):
                assert all(child.poll() is None for child in children),'child exited before synchronized ingest'
                assert time.monotonic()<deadline,'concurrent process readiness timeout'
                time.sleep(.01)
            gate.write_text('start')
            for child in children:
                out,err=child.communicate(timeout=20)
                assert child.returncode==0,(out,err)
                assert json.loads(out)['published'] in (0,1)
        finally:
            for child in children:
                if child.poll() is None:child.kill();child.communicate()
        reopened=projection(path)
        assert reopened.status()=={'published':1,'pending':[]}
        assert reopened.query(1,'u')==[{'id':'d','title':'new','folder':'child'}]
        assert reopened.query(0,'u')==[{'id':'d','title':'old','folder':'child'}]


def check_atomic_batches(projection):
    """Public batch atomicity, checked against literal retained and published state."""
    initial=small(0)['initial']
    def document(epoch,title):
        return fragment(epoch,0,1,[{'kind':'put_document','id':'d','folder':'child','title':title,'acl':None,'deleted':False}])
    expected_old=[{'id':'d','title':'old','folder':'child'}]
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'atomic.sqlite';store=projection(path,copy.deepcopy(initial))
        retained=fragment(3,0,2,[]);store.ingest([retained]);before=store.status()
        first=document(1,'first')
        invalid=fragment(2,0,1,[{'kind':'put_folder','id':'child','parent':'child','acl':None}])
        batch=[first,seal([first]),invalid,seal([invalid])];original=copy.deepcopy(batch)
        try:store.ingest(batch)
        except ValueError:pass
        else:raise AssertionError('invalid later snapshot did not reject whole ingest batch')
        assert batch==original,'ingest mutated caller messages'
        reopened=projection(path)
        assert reopened.status()==before,'earlier epoch or invalid evidence survived failed batch'
        assert reopened.query(0,'u')==expected_old
        try:reopened.query(1,'u')
        except ValueError:pass
        else:raise AssertionError('earlier publication survived failed later epoch')
        second=document(2,'second');reopened.ingest([first,seal([first]),second,seal([second])])
        assert projection(path).status()=={'published':2,'pending':[{'epoch':3,'parts':2,'received':[0],'sealed':False}]}
        assert projection(path).query(1,'u')==[{'id':'d','title':'first','folder':'child'}]
        assert projection(path).query(2,'u')==[{'id':'d','title':'second','folder':'child'}]
    for kind in ('fragment','seal'):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'duplicates.sqlite';store=projection(path,copy.deepcopy(initial))
            retained=fragment(3,0,2,[]);store.ingest([retained]);before=store.status()
            first=document(1,'first');different=document(1,'different')
            duplicate_pair=[first,different] if kind=='fragment' else [seal([first]),seal([different])]
            batch=[fragment(2,0,2,[])]+duplicate_pair
            try:store.ingest(copy.deepcopy(batch))
            except ValueError:pass
            else:raise AssertionError('contradictory same-batch '+kind+' replay accepted')
            assert projection(path).status()==before,'conflicting batch persisted evidence'
            assert projection(path).query(0,'u')==expected_old
            projection(path).ingest([first,seal([first])])
            assert projection(path).status()=={'published':1,'pending':[{'epoch':3,'parts':2,'received':[0],'sealed':False}]}

def cli_success_cases():return [('small-1',small(1)),('small-4',small(4))]
