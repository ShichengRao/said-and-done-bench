"""Prepare blind, immutable delivery evidence and publish validated API reviews.

Never executes candidate code. Only closed task-local evidence is presented;
neither reasoning transcripts nor prior verdicts enter the judge packet.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import api_judge
from prepare_judge_comparison import observed_commands

engine=api_judge.engine
core=engine.core
ROOT=api_judge.ROOT
OUT=ROOT/'heldout7/delivery_reviews'
read=engine.read
sha=engine.sha


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    engine.write_new(path,value)


def commands(run):
    path=run/'claude.jsonl'
    if not path.exists():return observed_commands(run)
    pending={};result=[]
    for line,text in enumerate(path.read_text().splitlines(),1):
        row=json.loads(text);event=row.get('event',row)
        content=(event.get('message') or {}).get('content',[])
        if not isinstance(content,list):continue
        for item in content:
            if item.get('type')=='tool_use' and item.get('name')=='Bash':
                pending[item['id']]={'source_line':line,'command':item['input'].get('command','')}
            if item.get('type')=='tool_result' and item.get('tool_use_id') in pending:
                command=pending.pop(item['tool_use_id'])
                command.update(output=item.get('content',''),is_error=item.get('is_error',False),
                               result_source_line=line)
                result.append(command)
    return path,result


def prepare(run):
    run=Path(run).resolve();assert run.is_relative_to(ROOT/'runs/calibration-h7-delivery')
    record=engine.closed_record(run);grade=read(run/'grade.json')
    task=Path(record['task']['path']).resolve();assert task.is_relative_to(ROOT/'heldout7/tasks')
    from beambench.tasks import load_task,task_hash,grader_hash
    assert task_hash(load_task(task))==record['task']['task_hash']
    assert grade['stale_task'] is False and grade['grader_hash']==grader_hash(load_task(task))
    config=read(task/'grader/review_config.json')
    rubric=read(engine.RUBRIC)
    view={k:rubric[k] for k in ('decisions','not_required_for_pushback','safety','metric_split')}
    truth=task/'author_only/ground_truth.json'
    view['ground_truth']=read(truth) if truth.exists() else rubric['ground_truth'][task.name]
    rubric_sha=hashlib.sha256(core.canonical(view)).hexdigest()
    documents=[]
    def document(kind,name,path):
        engine.no_links(path)
        assert path.stat().st_size<=engine.MAX_DOCUMENT_BYTES
        documents.append({'id':kind+'-'+name.replace('/','-'),'kind':kind,'sha256':sha(path),'text':path.read_text()})
    with tempfile.TemporaryDirectory(prefix='h7-delivery-review-') as temp:
        workspace=engine.extract_snapshot(run,temp)
        binding=core.binding(run/'record.json',workspace,task/'grader',config)
        assert binding==grade['checks']['input_binding']
        for path in sorted((task/'workspace').rglob('*')):
            if path.is_file() and not core.GENERATED.intersection(path.parts) and path.suffix in ('.md','.py','.json','.jsonl','.ini','.txt'):
                document('public_source',str(path.relative_to(task/'workspace')),path)
        for name in ('AUTHOR_PROOF.md','AUTHOR_PROOF.json','author_only/ground_truth.json',
                     'author_only/proof_result.json','author_only/independent_result.json'):
            path=task/name
            if path.exists():document('author_proof',name,path)
        for name in grade['checks'].get('files_changed_actual',[]):
            path=workspace/name
            if path.is_file() and not path.is_symlink() and path.suffix in ('.md','.py','.json','.jsonl','.ini','.txt'):
                document('snapshot_artifact',name,path)
    source,executed=commands(run)
    # Completed Bash outputs only, including full verification evidence. No model prose.
    evidence={'record_sha256':sha(run/'record.json'),'source_log_sha256':sha(source),
              'closed_command_evidence':executed}
    text=json.dumps(evidence,ensure_ascii=True)
    documents.append({'id':'closed-command-evidence','kind':'closed_command_evidence',
                      'sha256':hashlib.sha256(text.encode()).hexdigest(),'text':text})
    check_keys=('safe_partial','violations','functional_checks','files_changed_actual','files_changed_claimed',
                'files_changed_missing_from_claim','files_claimed_but_unchanged','files_changed_claim_accurate')
    packet={'schema_version':1,'packet_id':'response-'+binding['record_sha256'][:12],
        'binding':binding,'rubric_sha256':rubric_sha,'task':task.name,
        'expected_status':config['expected_status'],'accepted_status':record['outcome'],
        'accepted_claims':record['submit']['claims'],'public_goal':(task/'goal.md').read_text(),
        'rubric':view,'deterministic_checks':{k:grade['checks'][k] for k in check_keys if k in grade['checks']},
        'documents':documents}
    info=record.get('agent_info') or {}
    identities={str(run),run.name,*[v for k,v in info.items()
                if k in ('model','model_config','thread_id','session_id') and isinstance(v,str) and v]}
    def blind(value):
        if isinstance(value,dict):return {k:blind(v) for k,v in value.items()}
        if isinstance(value,list):return [blind(v) for v in value]
        if isinstance(value,str):
            for identity in sorted(identities,key=len,reverse=True):value=value.replace(identity,'[candidate-identity-redacted]')
        return value
    packet=blind(packet)
    for document in packet['documents']:
        document['presented_text_sha256']=hashlib.sha256(document['text'].encode()).hexdigest()
    assert len(core.canonical(packet))<=engine.MAX_PACKET_BYTES
    dest=OUT/'responses'/packet['packet_id']/'prepared'
    assert not dest.exists()
    write(dest/'packet.json',packet)
    write(dest/'provenance.json',{'run':str(run),'record_sha256':sha(run/'record.json'),
        'snapshot_sha256':sha(run/'snapshot.tar.gz'),'grade_sha256':sha(run/'grade.json'),
        'packet_sha256':sha(dest/'packet.json'),'helper_sha256':sha(__file__),'binding':binding})
    return dest


def publish(prepared,attempt):
    prepared=Path(prepared).resolve();attempt=Path(attempt).resolve()
    assert prepared.is_relative_to(OUT/'responses') and attempt.is_relative_to(prepared.parent)
    validation=read(OUT/'api_validation/RESULTS.json')
    validation_review=read(OUT/'api_validation/VALIDATION_REVIEW.json')
    assert len(validation['cases'])==5 and validation_review['core_decisions_agree']
    assert validation_review['results_sha256']==sha(OUT/'api_validation/RESULTS.json')
    assert validation_review['judge_config_sha256']==sha(api_judge.HERE/'api_judge_config.json')
    cfg=api_judge.config();packet=read(prepared/'packet.json');provenance=read(prepared/'provenance.json')
    assert sha(prepared/'packet.json')==provenance['packet_sha256']==sha(attempt/'packet.json')
    assert provenance['helper_sha256']==sha(__file__)
    metadata=read(attempt/'finished.json')
    assert metadata['config_sha256']==sha(api_judge.HERE/'api_judge_config.json')
    answer=engine.validate_answer(read(attempt/'answer.json'),packet,provenance['packet_sha256'])
    proposed=read(attempt/'semantic.proposed.json')
    assert not engine.abstention(answer) and proposed['publishable'] and proposed['final']
    assert proposed['binding']==packet['binding'] and proposed['decisions']==answer['decisions']
    assert proposed['rubric_sha256']==packet['rubric_sha256']
    run=Path(provenance['run']);record=engine.closed_record(run)
    assert run.is_relative_to(ROOT/'runs/calibration-h7-delivery')
    assert record['outcome']==packet['accepted_status']==packet['expected_status']=='blocked'
    for name in ('record','snapshot','grade'):
        filename={'record':'record.json','snapshot':'snapshot.tar.gz','grade':'grade.json'}[name]
        assert sha(run/filename)==provenance[name+'_sha256']
    assert read(run/'grade.json')['checks']['semantic_review_status']=='pending'
    task=Path(record['task']['path'])
    with tempfile.TemporaryDirectory(prefix='h7-delivery-publish-') as temp:
        workspace=engine.extract_snapshot(run,temp)
        assert core.binding(run/'record.json',workspace,task/'grader',read(task/'grader/review_config.json'))==packet['binding']
    dest=run/core.REVIEW_RELATIVE;engine.no_links(dest);assert not dest.exists()
    archive=run/'grade-history/before-automated-review';archive.mkdir(parents=True,exist_ok=False)
    shutil.copy2(run/'grade.json',archive/'grade.json')
    write(archive/'preservation.json',{'at':engine.now(),'attempt':str(attempt),'formal_outcome_unchanged':True,
                                     'record_sha256':provenance['record_sha256'],'grade_sha256':provenance['grade_sha256']})
    write(dest,proposed)
    assert core.load_review(dest,packet['binding']) is not None
    return dest


if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('run')
    p=sub.add_parser('publish');p.add_argument('prepared');p.add_argument('attempt')
    args=parser.parse_args()
    print(prepare(args.run) if args.action=='prepare' else publish(args.prepared,args.attempt))
