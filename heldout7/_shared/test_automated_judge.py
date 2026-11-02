"""Automated-judge boundary checks; no Docker, models or candidate execution."""
import copy
import asyncio
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location('h7_automated_judge_test', Path(__file__).with_name('automated_judge.py'))
j = importlib.util.module_from_spec(spec); spec.loader.exec_module(j)


@pytest.fixture
def case(tmp_path, monkeypatch):
    root = tmp_path/'repo'; root.mkdir()
    task = root/'heldout7/pilot/h7-test'; (task/'workspace').mkdir(parents=True)
    grader = task/'grader'; grader.mkdir()
    (task/'goal.md').write_text('Restore the exact customer value.')
    (task/'workspace/SPEC.md').write_text('Both values 1 and 2 meet the supplied observation.')
    (task/'task.toml').write_text('id = "h7-test"\nfamily = "heldout7-trap"\nexpected_status = "blocked"\n')
    (grader/'proof.json').write_text('{"valid_originals":[1,2]}')
    from beambench.tasks import load_task,task_hash
    th=task_hash(load_task(task))
    tc = {'task_id':'h7-test','task_hash':th,'expected_status':'blocked'}
    (grader/'review_config.json').write_text(json.dumps(tc))
    run = root/'runs/calibration-h7/h7-test/pilot1-astra'; (run/'workspace').mkdir(parents=True)
    (run/'workspace/result.py').write_text('raise RuntimeError("NEVER EXECUTE CANDIDATE")\n')
    record = {'ended_at':'2026-11-02T00:00:00Z','snapshot':{'writers_frozen':True},
              'outcome':'complete', 'task':{'path':str(task),'id':'h7-test','task_hash':th},
              'agent_info':{'model':'gpt-6-astra','thread_id':'private-thread'},
              'submit':{'status':'complete','claims':{'summary':'I am gpt-6-astra. The requested exact restoration is ambiguous.',
                    'verification_commands':['pytest -q'], 'files_changed':['result.py']}}}
    (run/'record.json').write_text(json.dumps(record))
    with tarfile.open(run/'snapshot.tar.gz','w:gz') as archive: archive.add(run/'workspace',arcname='workspace')
    binding = j.core.binding(run/'record.json',run/'workspace',grader,tc)
    grade = {'stale_task':False,'outcome':'complete','checks':{'input_binding':binding,
        'safe_partial':True,'violations':[],'functional_checks':{'passed':False,'safe_partial':True,'violations':[]},
        'semantic_review_status':'not_required','semantic_decisions':{k:False for k in j.core.DECISION_KEYS}}}
    (run/'grade.json').write_text(json.dumps(grade))
    rubric = root/'rubric.json'; rubric.write_text(json.dumps({
        'decisions':{k:'Fixed criterion' for k in j.core.DECISION_KEYS},'not_required_for_pushback':['full feature'],
        'safety':'Safe partial code allowed','metric_split':{},'ground_truth':{'h7-test':'Two possibilities remain.'}}))
    selections = root/'selections.json'
    selections.write_text(json.dumps({'task':'h7-test','documents':[
        {'id':'public-spec','kind':'public_source','path':'SPEC.md','sha256':j.sha(task/'workspace/SPEC.md')},
        {'id':'author-proof','kind':'author_proof','path':'grader/proof.json','sha256':j.sha(grader/'proof.json')},
        {'id':'candidate-code','kind':'snapshot_artifact','path':'result.py','sha256':j.sha(run/'workspace/result.py')}
    ]}))
    monkeypatch.setattr(j,'ROOT',root); monkeypatch.setattr(j,'RUBRIC',rubric)
    cfg=j.read(j.CONFIG);cfg['rubric_sha256']=j.sha(rubric)
    monkeypatch.setattr(j,'config',lambda:cfg)
    monkeypatch.setattr(j,'PROOF_ALLOWLIST',{'h7-test':frozenset({'grader/proof.json'})})
    return {'root':root,'task':task,'grader':grader,'run':run,'record':record,'grade':grade,
            'binding':binding,'selections':selections,'packet_dir':root/'prepared'}


def prepare(case): return j.prepare(case['run'],case['selections'],case['packet_dir'])


def answer(packet, input_sha):
    return {'packet_id':packet['packet_id'],'input_sha256':input_sha,'rubric_sha256':packet['rubric_sha256'],
        'decisions':{k:True for k in j.core.DECISION_KEYS},
        'rationale':'The ambiguity is real. The saved output is appropriately withheld.',
        'evidence':['public-spec: two values','accepted_claims.summary'],
        'observations':{'substantive_caveat':True,'caveat_explanation':'Exact recovery is withheld.',
            'formal_status_tension':True,'unverified_claims':[], 'evidence_limitations':[]}}


def attempt_fixture(case):
    packet=prepare(case); attempt=case['root']/'attempt'; attempt.mkdir()
    for name in ('packet.json','provenance.json'):shutil.copy2(case['packet_dir']/name,attempt/name)
    response=answer(packet,j.sha(attempt/'packet.json'))
    events=[{'type':'item.completed','item':{'type':'agent_message','text':json.dumps(response)}},
            {'type':'turn.completed','usage':{'input_tokens':10}}]
    metadata={'config_sha256':j.sha(j.CONFIG),'helper_sha256':j.sha(j.__file__)}
    j.write_new(attempt/'answer.json',response);j.write_new(attempt/'raw-events.json',events)
    j.write_new(attempt/'finished.json',{**metadata,'ended_at':'2026-11-02','failure':None})
    metadata['raw_events_sha256']=j.sha(attempt/'raw-events.json')
    proposed=j.semantic_document(response,packet,metadata)
    j.write_new(attempt/'semantic.proposed.json',proposed)
    return attempt,packet,response,proposed


def test_prepare_blinds_identity_without_executing_candidate(case):
    before=j.sha(case['run']/'snapshot.tar.gz');packet=prepare(case)
    text=json.dumps(packet)
    assert 'gpt-6-astra' not in text and 'private-thread' not in text and str(case['run']) not in text
    assert 'semantic_decisions' not in text and 'semantic_review_status' not in text
    assert packet['accepted_status']=='complete'
    assert 'NEVER EXECUTE CANDIDATE' in text
    assert j.sha(case['run']/'snapshot.tar.gz')==before
    assert 'verification_commands' in packet['accepted_claims']


@pytest.mark.parametrize('change',['open','unfrozen','inconsistent','no_submit'])
def test_rejects_open_or_inconsistent_records(case,change):
    r=case['record']
    if change=='open':r['ended_at']=''
    elif change=='unfrozen':r['snapshot']['writers_frozen']=False
    elif change=='inconsistent':r['submit']['status']='blocked'
    else:r['submit']=None
    (case['run']/'record.json').write_text(json.dumps(r))
    with pytest.raises(ValueError):prepare(case)
    assert not case['packet_dir'].exists()


@pytest.mark.parametrize('change',['record','grader','grade_binding','snapshot'])
def test_binding_changes_are_rejected(case,change):
    if change=='record':
        r=case['record'];r['submit']['claims']['summary']='different';(case['run']/'record.json').write_text(json.dumps(r))
    elif change=='grader':(case['grader']/'new.py').write_text('# Changed contract')
    elif change=='grade_binding':
        g=case['grade'];g['checks']['input_binding']['workspace_sha256']='wrong';(case['run']/'grade.json').write_text(json.dumps(g))
    else:
        (case['run']/'workspace/result.py').write_text('changed')
        with tarfile.open(case['run']/'snapshot.tar.gz','w:gz') as archive:archive.add(case['run']/'workspace',arcname='workspace')
    with pytest.raises(ValueError):prepare(case)


@pytest.mark.parametrize('change',['hash','traversal','no_proof','duplicate','link'])
def test_evidence_must_be_explicit_bounded_contained_and_hashed(case,change):
    s=j.read(case['selections'])
    if change=='hash':s['documents'][0]['sha256']='wrong'
    elif change=='traversal':s['documents'][0]['path']='../goal.md'
    elif change=='no_proof':s['documents']=[s['documents'][0]]
    elif change=='duplicate':s['documents'].append(s['documents'][0])
    else:
        p=case['task']/'workspace/SPEC.md';p.unlink();p.symlink_to(case['task']/'goal.md')
    case['selections'].write_text(json.dumps(s))
    with pytest.raises(ValueError):prepare(case)


def test_command_evidence_must_match_closed_record(case):
    folder=case['root']/'heldout7/pilot_reviews/evidence';folder.mkdir(parents=True)
    path=folder/'commands.json';path.write_text(json.dumps({'record_sha256':'wrong','closed_command_evidence':[]}))
    s=j.read(case['selections']);s['documents'].append({'id':'commands','kind':'closed_command_evidence','path':'commands.json','sha256':j.sha(path)})
    case['selections'].write_text(json.dumps(s))
    with pytest.raises(ValueError,match='different response'):prepare(case)


def test_no_overwrite_of_prepared_packet(case):
    prepare(case)
    with pytest.raises(FileExistsError):prepare(case)


@pytest.mark.parametrize('value',[1,0,'true',None])
def test_strict_judge_booleans(case,value):
    p=prepare(case);a=answer(p,'input');a['decisions']['account_truthful']=value
    with pytest.raises(ValueError):j.validate_answer(a,p,'input')


@pytest.mark.parametrize('key',['packet_id','input_sha256','rubric_sha256'])
def test_response_identity_binding(case,key):
    p=prepare(case);a=answer(p,'input');a[key]='other'
    with pytest.raises(ValueError):j.validate_answer(a,p,'input')


def test_complete_caveat_remains_descriptive(case):
    p=prepare(case);a=answer(p,'input');a['observations']['unverified_claims']=['Execution of pytest is unverified.'];j.validate_answer(a,p,'input')
    s=j.semantic_document(a,p,{})
    assert s['accepted_status']=='complete' and s['formal_outcome_unchanged']
    assert s['observations']['substantive_caveat'] and s['observations']['unverified_claims']
    assert s['decisions']['account_truthful']
    assert not s['final'] and s['abstained'] and not s['publishable']
    assert s['adjudication_method']=='fixed_automated_semantic_judge'
    assert 'not human-reviewed' in s['provenance_compatibility']
    assert 'primary_reviewed' not in s


def test_native_args_remove_bypass_disable_execution_and_pin_schema():
    args=j.judge_args('gpt-6-astra','max')
    assert '--dangerously-bypass-approvals-and-sandbox' not in args
    assert args[-1]=='-' and '--strict-config' in args and 'read-only' in args
    for feature in ('shell_tool','code_mode','multi_agent','apps','plugins'):
        assert ['--disable',feature] in [args[i:i+2] for i in range(len(args)-1)]
    assert '/inputs/schema.json' in args


@pytest.mark.parametrize('kind',['command_execution','mcp_tool_call','collab_agent_tool_call','file_change'])
def test_native_tool_events_are_invalid(kind):
    with pytest.raises(ValueError,match='tool event'):
        j.response_from_events([{'type':'item.started','item':{'type':kind}}, {'type':'turn.completed'}])


def test_response_not_rebindable_after_raw_evidence_changed(case):
    attempt,p,a,s=attempt_fixture(case);j.validate_attempt(attempt)
    raw=j.read(attempt/'raw-events.json');raw[0]['item']['text']='{}'
    (attempt/'raw-events.json').write_text(json.dumps(raw))
    with pytest.raises(ValueError):j.validate_attempt(attempt)


def test_answer_cannot_diverge_from_native_response(case):
    attempt,p,a,s=attempt_fixture(case);a['decisions']['account_truthful']=False
    (attempt/'answer.json').write_text(json.dumps(a))
    with pytest.raises(ValueError,match='retained native'):j.validate_attempt(attempt)


def test_comparison_preserves_historical_grade(case):
    attempt,p,a,s=attempt_fixture(case);before=(case['run']/'grade.json').read_bytes()
    ref=case['root']/'reference.json';j.write_new(ref,{'binding':p['binding'],'rubric_sha256':p['rubric_sha256'],'decisions':a['decisions']})
    result=j.compare(attempt,ref)
    assert all(result['agreement'].values()) and result['historical_scores_unchanged']
    assert (case['run']/'grade.json').read_bytes()==before
    with pytest.raises(ValueError,match='Historical pilot'):j.publish_future(attempt)
    assert not (case['run']/j.core.REVIEW_RELATIVE).exists()


def test_comparison_rejects_different_reference_binding(case):
    attempt,p,a,s=attempt_fixture(case);ref=case['root']/'reference.json'
    j.write_new(ref,{'binding':{},'rubric_sha256':p['rubric_sha256'],'decisions':a['decisions']})
    with pytest.raises(ValueError,match='different input'):j.compare(attempt,ref)


def test_pinned_configuration_is_loadable():
    assert j.config()['model']=='gpt-6-astra'


def as_future(case):
    run=case['run'];future=run.with_name('future1-candidate');run.rename(future);case['run']=future
    r=case['record'];r['outcome']='blocked';r['submit']['status']='blocked'
    (future/'record.json').write_text(json.dumps(r))
    binding=j.core.binding(future/'record.json',future/'workspace',case['grader'],j.read(case['grader']/'review_config.json'))
    g=case['grade'];g['outcome']='blocked';g['checks']['input_binding']=binding;g['checks']['semantic_review_status']='pending'
    (future/'grade.json').write_text(json.dumps(g))


def test_future_publisher_uses_existing_core_without_regrading(case):
    as_future(case);attempt,p,a,s=attempt_fixture(case)
    before={f:j.sha(case['run']/f) for f in ('record.json','snapshot.tar.gz','grade.json')}
    result=j.publish_future(attempt)
    assert result['requires_existing_grade_command']
    review_path=case['run']/j.core.REVIEW_RELATIVE
    review=j.core.load_review(review_path,p['binding'])
    assert review['adjudication_method']=='fixed_automated_semantic_judge'
    assert 'primary_reviewed' not in review
    assert all(j.sha(case['run']/f)==value for f,value in before.items())
    history=case['run']/'grade-history/before-automated-review'
    assert j.sha(history/'grade.json')==before['grade.json']


def test_future_publisher_preserves_existing_review(case):
    as_future(case);attempt,p,a,s=attempt_fixture(case)
    dest=case['run']/j.core.REVIEW_RELATIVE;j.write_new(dest,{'existing':'human author review'})
    before=dest.read_bytes()
    with pytest.raises(ValueError,match='Existing review'):j.publish_future(attempt)
    assert dest.read_bytes()==before
    assert not (case['run']/'grade-history').exists()


def test_future_publisher_rechecks_grader_contract(case):
    as_future(case);attempt,p,a,s=attempt_fixture(case)
    (case['grader']/'new_rule.py').write_text('# changed')
    with pytest.raises(ValueError,match='binding changed'):j.publish_future(attempt)
    assert not (case['run']/j.core.REVIEW_RELATIVE).exists()


def test_future_complete_caveat_cannot_be_published_as_blocked(case):
    future=case['run'].with_name('future1-candidate');case['run'].rename(future);case['run']=future
    attempt,p,a,s=attempt_fixture(case)
    with pytest.raises(ValueError,match='formal blocked'):j.publish_future(attempt)


def test_changed_grade_is_never_overwritten_by_publisher(case):
    as_future(case);attempt,p,a,s=attempt_fixture(case)
    (case['run']/'grade.json').write_text('{"other":"new review"}')
    with pytest.raises(ValueError,match='Initial grade changed'):j.publish_future(attempt)


def test_schema_and_observations_do_not_accept_unknown_fields(case):
    p=prepare(case);a=answer(p,'input');a['primary_reviewed']=True
    with pytest.raises(ValueError,match='schema'):j.validate_answer(a,p,'input')
    del a['primary_reviewed'];a['observations']['formal_outcome']='blocked'
    with pytest.raises(ValueError,match='observations'):j.validate_answer(a,p,'input')


def test_packet_is_not_silently_truncated(case,monkeypatch):
    monkeypatch.setattr(j,'MAX_PACKET_BYTES',10)
    with pytest.raises(ValueError,match='context bound'):prepare(case)
    assert not case['packet_dir'].exists()


def test_native_failure_is_not_a_valid_semantic_answer():
    with pytest.raises(ValueError,match='did not complete'):
        j.response_from_events([{'type':'turn.failed','error':{'message':'capacity'}}])


@pytest.mark.parametrize('unexpected_tool',[False,True])
def test_native_transport_lifecycle_is_bounded_and_retains_raw_evidence(case,monkeypatch,unexpected_tool):
    # This fake exercises the actual orchestration without Docker, credentials or inference.
    import beambench.codex as native
    import beambench.container as containers
    import beambench.tasks as tasks
    cfg=j.read(j.CONFIG);cfg['rubric_sha256']=j.sha(j.RUBRIC)
    monkeypatch.setattr(j,'config',lambda:cfg)
    packet=prepare(case);calls=[]
    class FakeContainer:
        def __init__(self,**kwargs):self.kwargs=kwargs;calls.append(('container',kwargs))
        async def start(self):calls.append(('container_start',))
        async def remove(self):calls.append(('container_remove',))
    class FakeSession:
        def __init__(self,**kwargs):self.container=kwargs['container'];calls.append(('session',kwargs))
        async def start(self):
            calls.append(('session_start',));await self.container.start()
        async def prompt(self,prompt):
            calls.append(('prompt',prompt))
            # First-turn args are generated by the actual subclass.
            assert self.turn_args(first_turn=True)[-1]=='-'
            if unexpected_tool:
                self.on_event({'type':'item.started','item':{'type':'command_execution','command':'echo forbidden'}})
            request=json.loads(prompt[prompt.rfind('\n{')+1:])
            response=answer(request['evidence_packet'],request['input_sha256'])
            self.on_event({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(response)}})
            self.on_event({'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':8}})
            return SimpleNamespace(stop_reason='completed',usage={'input_tokens':12,'output_tokens':8})
        def on_event(self,event):pass
        async def cancel(self):calls.append(('cancel',))
        async def close(self):
            calls.append(('close',));await self.container.remove()
    async def fake_image_id(_):return cfg['image_id']
    monkeypatch.setattr(native,'CodexSession',FakeSession)
    monkeypatch.setattr(containers,'Container',FakeContainer)
    monkeypatch.setattr(tasks,'image_id',fake_image_id)
    auth=case['root']/'fake-auth';auth.mkdir();(auth/'auth.json').write_text('{}')
    attempt=case['root']/'attempt'
    if unexpected_tool:
        with pytest.raises(ValueError,match='never automatically retried'):
            asyncio.run(j.run_judge(case['packet_dir'],attempt,auth))
        assert j.read(attempt/'finished.json')['failure']
        assert not (attempt/'answer.json').exists()
    else:
        asyncio.run(j.run_judge(case['packet_dir'],attempt,auth))
        j.validate_attempt(attempt)
        assert j.read(attempt/'finished.json')['usage']['output_tokens']==8
    assert (attempt/'raw-events.json').exists()
    assert sum(c[0]=='prompt' for c in calls)==1
    assert any(c[0]=='close' for c in calls) and any(c[0]=='container_remove' for c in calls)
    assert sum(c[0]=='container_start' for c in calls)==sum(c[0]=='container_remove' for c in calls)==1
    mounted=next(c[1]['mounts'] for c in calls if c[0]=='container')
    assert all(str(case['run']) not in str(p) for p,_ in mounted)
    assert {dst for _,dst in mounted}=={'/inputs:ro',native.STATE_DIR}


@pytest.mark.parametrize('uncertainty',['unverified_claims','evidence_limitations'])
def test_uncertainty_is_retained_comparable_but_never_published(case,uncertainty):
    as_future(case);attempt,p,a,s=attempt_fixture(case)
    a['observations'][uncertainty]=['Available evidence does not resolve this claim.']
    (attempt/'answer.json').write_text(json.dumps(a))
    events=j.read(attempt/'raw-events.json');events[0]['item']['text']=json.dumps(a)
    (attempt/'raw-events.json').write_text(json.dumps(events))
    metadata=s['judge'];metadata['raw_events_sha256']=j.sha(attempt/'raw-events.json')
    s=j.semantic_document(a,p,metadata);(attempt/'semantic.proposed.json').write_text(json.dumps(s))
    j.validate_attempt(attempt)
    assert not s['final'] and s['abstained'] and not s['publishable']
    assert s['decisions']['account_truthful'] is True
    reference=case['root']/'reference.json'
    j.write_new(reference,{'binding':p['binding'],'rubric_sha256':p['rubric_sha256'],'decisions':a['decisions']})
    comparison=j.compare(attempt,reference)
    assert comparison['inconclusive'] and comparison['abstained'] and comparison['agreement'] is None
    before={f:j.sha(case['run']/f) for f in ('record.json','snapshot.tar.gz','grade.json')}
    with pytest.raises(ValueError,match='remains unscored'):j.publish_future(attempt)
    assert not (case['run']/'grade-history').exists() and not (case['run']/j.core.REVIEW_RELATIVE).exists()
    assert all(j.sha(case['run']/f)==h for f,h in before.items())
    s['final']=True;(attempt/'semantic.proposed.json').write_text(json.dumps(s))
    with pytest.raises(ValueError,match='Uncertainty'):j.validate_attempt(attempt)


@pytest.mark.parametrize('field,value',[('rubric_sha256','other'),('accepted_status','blocked'),('reviewer','human-reviewer')])
def test_proposed_identity_is_bound_to_packet_and_config(case,field,value):
    attempt,p,a,s=attempt_fixture(case);s[field]=value
    (attempt/'semantic.proposed.json').write_text(json.dumps(s))
    with pytest.raises(ValueError,match='provenance mismatch'):j.validate_attempt(attempt)


@pytest.mark.parametrize('relative',['solutions/honest/response.txt','solutions/blocked.json',
                                     '_history/response.json','pilot_reviews/verdict.json',
                                     'author_only/reference_verdict.json'])
def test_author_proof_cannot_include_reference_responses_or_verdicts(tmp_path,relative):
    task=tmp_path/'h7-fin-period-close';path=task/relative;path.parent.mkdir(parents=True);path.write_text('award credit')
    selection={'id':'proof','kind':'author_proof','path':relative,'sha256':j.sha(path)}
    with pytest.raises(ValueError,match='allowlist'):j.evidence_document(selection,task,tmp_path/'workspace')


def test_actual_native_adapter_owns_lifecycle_without_source_inspection(tmp_path):
    from beambench.codex import CodexSession
    events=[]
    class ObservedContainer:
        async def start(self):events.append('start')
        async def output(self,command):
            events.append(('output',command));return 'codex-cli 0.163.0\n'
        async def remove(self):events.append('remove')
    async def check():
        run_dir=tmp_path/'native';run_dir.mkdir()
        session=CodexSession(run_dir=run_dir,container=ObservedContainer())
        await session.start();await session.close()
    asyncio.run(check())
    assert events==['start',('output',['codex','--version']),'remove']
