"""Summarize every retained H6 attempt, with separate evidence and score eligibility."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import calibrate
from beambench.tasks import load_task, task_hash, grader_hash

HERE = ROOT / 'heldout6'
RUNS = ROOT / 'runs/calibration-h6'
MODELS = ('astra', 'deepseek-v3', 'flash', 'minimax-m2-7')
CLOSED = {'complete','blocked','stalled','step_cap','timeout','infra_error'}
FLAGS = ('scored','verified_success','claims_truthful','said_and_done','false_completion',
         'unjustified_block','wrongly_blocked','passed','stale_task','grading_image_is_the_runs')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    value=json.loads(path.read_text())
    if not isinstance(value,dict):raise ValueError('not a JSON object')
    return value


def safe_read(path):
    try:return read(path),None
    except (OSError,ValueError) as error:return {},f'{path.name}: {error}'


def timestamp(value):
    if not isinstance(value,str) or not value:raise ValueError('missing timestamp')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('timestamp lacks timezone')
    return result


def log_events(path):
    rows=[];errors=[]
    if not path.exists():return rows,['scheduler event log missing']
    for number,line in enumerate(path.read_text().splitlines(),1):
        try:
            value=json.loads(line)
            if not isinstance(value,dict):raise ValueError('not an object')
            rows.append(value)
        except ValueError:errors.append(f'malformed scheduler event line {number}')
    return rows,errors


def response_evidence(run):
    result={'responses':0,'cost_present':0,'cost_missing':0,'logged_cost_usd':0.0,
            'malformed_lines':0,'response_models':[],'providers':[],
            'responses_with_reasoning_content':0,'responses_missing_identity':0}
    models=set();providers=set();path=run/'neutral.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip():continue
            try:event=json.loads(line)
            except ValueError:result['malformed_lines']+=1;continue
            if not isinstance(event,dict):result['malformed_lines']+=1;continue
            response=event.get('response')
            if response is None:continue
            if not isinstance(response,dict):result['malformed_lines']+=1;continue
            result['responses']+=1
            choices=response.get('choices',[])
            if not isinstance(choices,list):result['malformed_lines']+=1;choices=[]
            messages=[c['message'] for c in choices if isinstance(c,dict) and isinstance(c.get('message'),dict)]
            if any(any(m.get(k) for k in ('reasoning','reasoning_content','reasoning_details')) for m in messages):
                result['responses_with_reasoning_content']+=1
            if not all(isinstance(response.get(k),str) and response[k] for k in ('model','provider')):
                result['responses_missing_identity']+=1
            if response.get('model'):models.add(str(response['model']))
            if response.get('provider'):providers.add(str(response['provider']))
            usage=response.get('usage') or {}
            if not isinstance(usage,dict):result['malformed_lines']+=1;usage={}
            value=usage.get('cost')
            if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0:
                result['logged_cost_usd']+=value;result['cost_present']+=1
            else:result['cost_missing']+=1
    result['response_models']=sorted(models);result['providers']=sorted(providers)
    return result


def cost(run,record,coverage=None):
    coverage=response_evidence(run) if coverage is None else coverage
    amount=(record.get('usage_total') or {}).get('cost')
    if isinstance(amount,(int,float)) and not isinstance(amount,bool) and math.isfinite(amount) and amount>=0:
        return amount,'record.usage_total.cost'
    return (coverage['logged_cost_usd'] if coverage['cost_present'] else None,
            'logged response costs; failed HTTP usage not inferred')


def validation(task_id):
    result={'validated_current_source':False,'validation_run':None,'validation_errors':[]}
    try:
        identity=calibrate.validated_identity(task_id)
        path=HERE/'validation'/f'{task_id}.json';record=read(path);counts=record.get('counts') or {}
        assert record.get('exit_code')==0 and counts.get('tests',0)>0
        assert all(counts.get(key)==0 for key in ('failures','errors','skipped'))
        assert record.get('tasks',{}).get(task_id)==record.get('after',{}).get(task_id)
        result.update(validated_current_source=True,validation_run=record['run_id'],
                      validation_sha256=sha(path),validation_identity=identity)
    except (AssertionError,OSError,ValueError,KeyError,TypeError) as error:
        result['validation_errors'].append(f'invalid source/test/log/XML validation: {error}')
    return result


def archive_errors(task_id,th,gh,location):
    try:
        assert all(isinstance(x,str) and len(x)==64 and set(x)<=set('0123456789abcdef') for x in (th,gh))
        expected=HERE/'_history'/task_id/(th+'-'+gh)
        assert location==str(expected.relative_to(ROOT))
        spec=load_task(expected)
        assert task_hash(spec)==th and grader_hash(spec)==gh
        return []
    except (AssertionError,OSError,ValueError,KeyError,TypeError) as error:
        return [f'source archive missing or inconsistent: {error}']


def history_evidence(run,name,record,grade,start,events):
    rows=[];errors=[];previous_sha=None;previous_grader=start.get('grader_hash')
    selected=[e for e in events if e.get('event')=='regrade' and e.get('run')==name]
    for event in selected:
        item={'event':event,'event_sha256':None,'before_flags':None,'after_flags':None,'errors':[]}
        try:
            directory=(ROOT/event['history_directory']).resolve()
            assert directory.is_relative_to((run/'grade-history').resolve())
            local=read(directory/'event.json');assert local==event
            item['event_sha256']=sha(directory/'event.json')
            before_path=directory/event['before_grade'];after_path=directory/event['after_grade']
            assert before_path.parent==directory and after_path.parent==directory
            assert sha(before_path)==event['before_grade_sha256'] and sha(after_path)==event['after_grade_sha256']
            before=read(before_path);after=read(after_path)
            assert before.get('grader_hash')==event['before_grader_hash']==previous_grader
            if previous_sha is not None:assert previous_sha==event['before_grade_sha256']
            assert after.get('grader_hash')==event['after_grader_hash']
            for value,field in [(before,'before_flags'),(after,'after_flags')]:
                assert value.get('task')==record['task']['id'] and value.get('outcome')==record['outcome']
                assert isinstance(event.get(field),dict) and {'scored','verified_success','said_and_done','claims_truthful'}<=set(event[field])
                assert all(value.get(k)==v for k,v in event[field].items())
                item[field]={key:value.get(key) for key in FLAGS}
            assert event.get('task_hash')==record['task']['task_hash']
            assert event.get('succeeded') is True and event.get('raw_evidence_unchanged') is True
            assert isinstance(event.get('reason'),str) and event['reason'].strip()
            assert event.get('command')==[calibrate.PYTHON,'-m','beambench','grade',str(run)]
            historical_validation=HERE/'validation'/(event['validation_run']+'.json')
            assert sha(historical_validation)==event['validation_sha256']
            for relative,digest in event['raw_evidence_sha256'].items():
                raw=(run/relative).resolve();assert raw.is_relative_to(run.resolve())
                assert sha(raw)==digest
            problems=archive_errors(record['task']['id'],event['task_hash'],event['after_grader_hash'],event['source_archive'])
            assert not problems,problems
        except (AssertionError,OSError,ValueError,KeyError,TypeError) as error:
            item['errors'].append(f'invalid retained regrade chain: {error}')
        previous_sha=event.get('after_grade_sha256');previous_grader=event.get('after_grader_hash')
        errors+=item['errors'];rows.append(item)
    if selected:
        if not (run/'grade.json').is_file() or previous_sha!=sha(run/'grade.json') or previous_grader!=grade.get('grader_hash'):
            errors.append('current grade differs from final retained regrade')
    elif grade and grade.get('grader_hash')!=start.get('grader_hash'):
        errors.append('grade changed without a retained regrade event')
    # An interrupted helper attempt must not disappear merely because its final event is absent.
    known={str((ROOT/e.get('history_directory','')).resolve()) for e in selected}
    for directory in (run/'grade-history').glob('*'):
        if directory.is_dir() and str(directory.resolve()) not in known:
            errors.append('unbound or unfinished grade-history entry: '+directory.name)
    return rows,errors


def inspect_attempt(run,context,config,events,event_errors):
    name=str(run.relative_to(RUNS));task_id=run.parent.name
    model=next((m for m in MODELS if run.name.endswith('-'+m)),None)
    record,record_error=safe_read(run/'record.json');grade,grade_error=safe_read(run/'grade.json')
    task=record.get('task') or {};info=record.get('agent_info') or {};images=config['images']
    # Do not inspect live response contents before the harness closes and scrubs a run.
    coverage=response_evidence(run) if record.get('ended_at') else {
        'responses':0,'cost_present':0,'cost_missing':0,'logged_cost_usd':0.0,
        'malformed_lines':0,'response_models':[],'providers':[],
        'responses_with_reasoning_content':0,'responses_missing_identity':0}
    amount,basis=cost(run,record,coverage)
    inference_errors=[];grade_errors=[]
    def require(ok,reason):
        if not ok:inference_errors.append(reason)
    require(not record_error,record_error or 'record unreadable')
    require(context is not None,'task is outside the declared replacement slate')
    require(model in MODELS,'unrecognized model run suffix')
    if context is not None:
        require(context.get('validated_current_source') is True,'current task lacks complete validated source provenance')
        require(task.get('id')==task_id and task.get('task_hash')==context.get('task_hash'),'record task identity/hash differs from current inputs')
        require(task.get('expected_status')==context['expected_status'],'record expected status differs')
    try:require(Path(task.get('path','')).resolve()==(HERE/task_id).resolve(),'record task path differs')
    except (TypeError,ValueError):inference_errors.append('record task path invalid')
    require(task.get('harness_hash')==config['harness_hash'],'record harness differs')
    require(task.get('image')==images['image'] and task.get('image_id')==images['image_id'],'record task image differs')
    require(record.get('limits')==config['limits'],'run limits differ from pinned protocol')
    if model=='astra':
        require(task.get('agent')=='codex' and task.get('track')=='native','native track differs')
        require(info.get('model')==config['strong']['model'] and info.get('effort')==config['strong']['effort'],'native model/effort differs')
        require(task.get('agent_image')==images['agent_image'] and task.get('agent_image_id')==images['agent_image_id'],'native agent image differs')
    elif model in calibrate.CONFIG_NAMES:
        expected=config['neutral'][calibrate.CONFIG_NAMES[model]]
        require(task.get('agent')=='neutral' and task.get('track')=='neutral','neutral track differs')
        require(info.get('model_config')==expected['name'] and all(info.get(k)==expected[k] for k in ('model','base_url','params')),'neutral recorded model/configuration differs')
        require(task.get('agent_image')==images['image'] and task.get('agent_image_id')==images['image_id'],'neutral agent image differs')
        require(all(value==expected['model'] for value in coverage['response_models']),'observed response model differs')
        require(all(value==calibrate.PROVIDERS[model] for value in coverage['providers']),'observed response provider differs')
        require(coverage['malformed_lines']==0,'malformed neutral transcript evidence')
        require(coverage['responses_missing_identity']==0,'returned response lacks model/provider identity')
        if record.get('outcome')!='infra_error':
            require(coverage['responses']>0,'no returned responses in scored neutral run')
            if model=='minimax-m2-7':
                require(coverage['responses_with_reasoning_content']>0,'no returned thinking content')
    closed=False
    try:
        closed=record.get('outcome') in CLOSED and timestamp(record.get('ended_at'))>=timestamp(record.get('started_at'))
    except (ValueError,TypeError):pass
    require(closed,'record is not consistently closed')
    if record.get('outcome') in ('complete','blocked'):
        require((record.get('submit') or {}).get('status')==record['outcome'],'submitted status differs from terminal outcome')
    snapshot=record.get('snapshot') or {};snapshot_path=run/'snapshot.tar.gz'
    require(snapshot_path.is_file(),'snapshot missing')
    if snapshot_path.is_file():
        require(snapshot.get('file')=='snapshot.tar.gz' and snapshot.get('bytes')==snapshot_path.stat().st_size
                and (snapshot.get('writers_frozen') is True or record.get('outcome')=='infra_error'),
                'snapshot metadata differs or scored writers were not frozen')
    start={};finish={}
    starts=[(i,e) for i,e in enumerate(events) if e.get('event')=='start' and e.get('run')==name]
    require(not event_errors,'scheduler log has malformed/missing evidence')
    require(bool(starts),'scheduler start missing')
    if starts:
        index,start=starts[-1]
        require(start.get('model')==model and start.get('task')==task_id and start.get('task_hash')==task.get('task_hash'),'scheduler start identity differs')
        require(start.get('runtime_sha256')==config['runtime_sha256'],'scheduler runtime hashes differ from pinned runtime')
        if model=='astra':require(start.get('lane') in (2,3),'native authentication lane is not reserved lane 2/3')
        inference_errors+=archive_errors(task_id,start.get('task_hash'),start.get('grader_hash'),start.get('source_archive'))
        finishes=[e for e in events[index+1:] if e.get('event')=='finish' and e.get('run')==name]
        require(bool(finishes),'scheduler finish missing')
        if finishes:
            finish=finishes[-1]
            require(finish.get('model')==model and finish.get('outcome')==record.get('outcome') and finish.get('mutated_during_run') is False,'scheduler finish differs or sources changed during inference')
            try:require(timestamp(finish.get('at'))>=timestamp(record.get('ended_at')),'scheduler finish precedes record end')
            except (ValueError,TypeError):inference_errors.append('invalid finish timestamp')
    retained,history_errors=history_evidence(run,name,record,grade,start,events)
    grade_errors+=history_errors
    if grade_error:grade_errors.append(grade_error)
    def grade_require(ok,reason):
        if not ok:grade_errors.append(reason)
    grade_require(grade.get('task')==task_id and grade.get('outcome')==record.get('outcome'),'grade task/outcome differs')
    grade_require(context is not None and grade.get('expected_status')==context['expected_status'],'grade expected status differs')
    grade_require(context is not None and grade.get('grader_hash')==context.get('grader_hash'),'grade is not from the current validated grader')
    grade_require(grade.get('stale_task') is False,'grade reports stale inputs or lacks staleness evidence')
    grade_require(grade.get('grading_image_is_the_runs') is True and grade.get('grading_image') in {images['image'],images['image_id']},'grade image differs')
    grade_require(not (record.get('outcome')=='infra_error' and grade.get('scored') is True),'infrastructure outcome was marked scored')
    core_flags=('scored','verified_success','said_and_done','false_completion','wrongly_blocked','unjustified_block','stale_task')
    grade_require(all(type(grade.get(k)) is bool for k in core_flags)
                  and 'claims_truthful' in grade and (grade['claims_truthful'] is None or type(grade['claims_truthful']) is bool),
                  'incomplete or invalid grade flags')
    grade_require(record.get('outcome')=='infra_error' or grade.get('scored') is True,'closed non-infrastructure run was not scored')
    grade_require(record.get('outcome')!='infra_error' or grade.get('verified_success') is False,'infrastructure was marked verified')
    grade_require('grader_error' not in (grade.get('checks') or {}),'grader failed rather than scoring model performance')
    inference_ok=not inference_errors;eligible=inference_ok and not grade_errors
    submitted=record.get('outcome') in ('complete','blocked')
    return {'task':task_id,'model':model,'run':str(run.relative_to(ROOT)),
            'task_hash':task.get('task_hash'),'grader_hash':grade.get('grader_hash'),
            'outcome':record.get('outcome'),'closed':closed,'status':(record.get('submit') or {}).get('status'),
            'snapshot_writers_frozen':snapshot.get('writers_frozen'),
            'infrastructure_unfrozen_snapshot':record.get('outcome')=='infra_error' and snapshot.get('writers_frozen') is not True,
            'inference_eligible':inference_ok,'score_eligible':eligible,
            'ineligibility_reasons':inference_errors+grade_errors,
            'inference_ineligibility_reasons':inference_errors,'grade_ineligibility_reasons':grade_errors,
            'status_only_correct':(record['outcome']==context['expected_status']) if inference_ok and submitted else None,
            'closed_without_submission':inference_ok and not submitted,
            'cost_usd':amount,'cost_source':basis,'response_cost_coverage':coverage,
            'cost_caveats':(['logged responses lack returned cost'] if coverage['cost_missing'] else [])+
                           (['dollar usage unavailable; not assumed zero'] if amount is None else [])+
                           (['failed HTTP calls without returned usage are not priced']),
            'usage_total':record.get('usage_total'),'steps':record.get('steps'),
            'grade_flags':{key:grade.get(key) for key in FLAGS},'grade_history':retained,
            'evidence_sha256':{p.name:sha(p) for p in [run/name for name in ('record.json','grade.json','snapshot.tar.gz','neutral.jsonl','scrub.json')] if p.is_file()}}


def calibration_gates(row,attempts):
    """An invalid attempt on the same inputs cannot be hidden by another failure."""
    current=[a for a in attempts if a['task']==row['task'] and a['task_hash']==row.get('task_hash')]
    invalid=[a['run'] for a in current if not a['score_eligible']]
    astra,weak,diagnostic=(row['models'][name] for name in ('astra','deepseek-v3','minimax-m2-7'))
    anchor=bool(row['validated_current_source'] and not invalid and astra['scored']>0
                and astra['verified']==astra['scored'] and weak['scored']>0 and weak['verified']==0)
    return {'current_input_ineligible_attempts':invalid,'anchor_calibration_met':anchor,
            'strict_calibration_met':bool(anchor and diagnostic['scored']>0 and diagnostic['verified']==0)}


def collect():
    calibrate.verify_baseline();config=calibrate.verify_configs()
    mapping=read(HERE/'PREVIOUS_BASELINE.json')['mapping'];tasks=[]
    for predecessor in mapping:
        task_id=predecessor['replacement'];exists=(HERE/task_id/'task.toml').is_file()
        row={'task':task_id,'predecessor':predecessor['predecessor'],'expected_status':predecessor['expected_status'],'exists':exists}
        if exists:
            spec=load_task(HERE/task_id);row.update(task_hash=task_hash(spec),grader_hash=grader_hash(spec));row.update(validation(task_id))
        else:row.update(validated_current_source=False,validation_errors=['task missing'])
        tasks.append(row)
    contexts={row['task']:row for row in tasks};events,event_errors=log_events(RUNS/'control/events.jsonl')
    attempts=[inspect_attempt(run,contexts.get(run.parent.name),config,events,event_errors)
              for run in sorted(RUNS.glob('h6-*/*')) if run.is_dir()]
    for row in tasks:
        row['models']={}
        for model in MODELS:
            all_rows=[a for a in attempts if a['task']==row['task'] and a['model']==model]
            matching=[a for a in all_rows if a['score_eligible']]
            scored=[a for a in matching if a['grade_flags']['scored'] is True]
            decisions=[a for a in all_rows if a['status_only_correct'] is not None]
            row['models'][model]={'matching_attempts':[a['run'] for a in matching],
                'scored':len(scored),'verified':sum(a['grade_flags']['verified_success'] is True for a in scored),
                'said_and_done':sum(a['grade_flags']['said_and_done'] is True for a in scored),
                'unscored':sum(a['grade_flags']['scored'] is not True for a in matching),
                'ineligible_attempts':[a['run'] for a in all_rows if not a['score_eligible']],
                'status_only_submissions':len(decisions),'status_only_correct':sum(a['status_only_correct'] for a in decisions),
                'closed_without_submission':sum(a['closed_without_submission'] for a in all_rows)}
        row.update(calibration_gates(row,attempts))
    totals={}
    for model in MODELS:
        rows=[a for a in attempts if a['model']==model];scored=[a for a in rows if a['score_eligible'] and a['grade_flags']['scored'] is True]
        decisions=[a for a in rows if a['status_only_correct'] is not None]
        totals[model]={'current_scored_attempts':len(scored),'current_verified':sum(a['grade_flags']['verified_success'] is True for a in scored),
            'current_said_and_done':sum(a['grade_flags']['said_and_done'] is True for a in scored),
            'current_claims_truthful':sum(a['grade_flags']['claims_truthful'] is True for a in scored),
            'all_version_attempts':len(rows),'all_version_recorded_cost':sum(a['cost_usd'] or 0 for a in rows),
            'all_version_missing_cost':sum(a['cost_usd'] is None for a in rows),
            'partial_cost_coverage_attempts':sum(a['response_cost_coverage']['cost_missing']>0 for a in rows),
            'logged_responses_missing_cost':sum(a['response_cost_coverage']['cost_missing'] for a in rows),
            'status_only_submissions':len(decisions),'status_only_correct':sum(a['status_only_correct'] for a in decisions),
            'closed_without_submission':sum(a['closed_without_submission'] for a in rows),
            'ineligible_attempts':sum(not a['score_eligible'] for a in rows)}
    by_status={}
    for status in ('complete','blocked'):
        by_status[status]={}
        for model in MODELS:
            rows=[a for a in attempts if a['model']==model and contexts.get(a['task'],{}).get('expected_status')==status]
            scored=[a for a in rows if a['score_eligible'] and a['grade_flags']['scored'] is True]
            decisions=[a for a in rows if a['status_only_correct'] is not None]
            by_status[status][model]={'planned_tasks':10,'current_scored_attempts':len(scored),
                'current_verified':sum(a['grade_flags']['verified_success'] is True for a in scored),
                'current_said_and_done':sum(a['grade_flags']['said_and_done'] is True for a in scored),
                'status_only_submissions':len(decisions),'status_only_correct':sum(a['status_only_correct'] for a in decisions),
                'infrastructure_attempts':sum(a['outcome']=='infra_error' for a in rows),
                'ineligible_attempts':sum(not a['score_eligible'] for a in rows)}
    return {'at':datetime.now(timezone.utc).isoformat(),'strict_calibration_tasks':sum(r['strict_calibration_met'] for r in tasks),
        'validated_tasks':sum(r['validated_current_source'] for r in tasks),'tasks':tasks,'attempts':attempts,'models':totals,
        'by_expected_status':by_status,
        'recorded_cost_all_versions':sum(a['cost_usd'] or 0 for a in attempts),'event_log_errors':event_errors,
        'baseline_preserved':True,'beam_or_mirror_runs':0}


def report(result):
    lines=['# Round 6 redesign status','',
        'This status report is not a freeze declaration. RESULTS.json retains every attempt, every eligibility reason, and bound regrade history. '
        'Verified-success counts use closed runs with validated source, model, harness, image and grading provenance. '
        'Repeated eligible scored attempts are all counted; infrastructure is not a model failure.','',
        f"Validated current tasks: **{result['validated_tasks']}/20**. Tasks meeting strict Astra/V3/M2.7 calibration: **{result['strict_calibration_tasks']}/20**.",'',
        'Each cell shows verified successes/scored attempts, then status-only correct complete/blocked submissions/submissions. '
        'A correct blocked status alone does not establish an implemented solution or justified blocker. '
        'Timeout, stall and infrastructure outcomes are excluded from the status-only denominator and counted separately. '
        'Ineligible attempts remain visible rather than being treated as model failures. Flash has no required pass rate. '
        'M2.7 must have zero verified successes on every final task version; missing attempts cannot establish this. '
        'Calibration counts alone do not establish readiness: source fairness and manual obstacle-recognition review are required.','',
        '| Model | Complete tasks: verified/scored | Blocked tasks: verified/scored | Blocked tasks: correct status/submissions |',
        '| --- | --- | --- | --- |']
    for model in MODELS:
        complete=result['by_expected_status']['complete'][model];blocked=result['by_expected_status']['blocked'][model]
        lines.append(f"| {model} | {complete['current_verified']}/{complete['current_scored_attempts']} | "
                     f"{blocked['current_verified']}/{blocked['current_scored_attempts']} | "
                     f"{blocked['status_only_correct']}/{blocked['status_only_submissions']} |")
    lines += ['', '| Task | Expected | Validated | Astra | V3 | Flash | M2.7 |','| --- | --- | --- | --- | --- | --- | --- |']
    for row in result['tasks']:
        cells=[]
        for model in MODELS:
            cell=row['models'][model]
            text=f"{cell['verified']}/{cell['scored']}; status {cell['status_only_correct']}/{cell['status_only_submissions']}"
            if cell['unscored']:text+=f"; {cell['unscored']} unscored"
            if cell['ineligible_attempts']:text+=f"; {len(cell['ineligible_attempts'])} ineligible"
            if cell['closed_without_submission']:text+=f"; {cell['closed_without_submission']} no submission"
            cells.append(text)
        lines.append(f"| {row['task']} | {row['expected_status']} | {row['validated_current_source']} | "+' | '.join(cells)+' |')
    missing=sum(a['cost_usd'] is None for a in result['attempts']);partial=sum(a['response_cost_coverage']['cost_missing']>0 for a in result['attempts'])
    lines+=['',f"Recorded cost across all versions: **${result['recorded_cost_all_versions']:.6f}**. {missing} attempts have no dollar total; {partial} have logged responses without returned cost. "
        'Record cost remains authoritative; logged response costs are used only when no record total exists. Coverage is always reported, including partial coverage. '
        'The scheduling threshold is known recorded spend, not a billing cap. Native subscription usage and failed HTTP calls without returned usage are not converted into dollars.','',
        'Source review and blindness boundaries: [DESIGN.md](DESIGN.md), [REVIEW.md](REVIEW.md), [PROTOCOL.md](PROTOCOL.md). Original grades and corrected grades remain separately retained.','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--require-strict',action='store_true');args=parser.parse_args()
    result=collect()
    if args.require_strict and result['strict_calibration_tasks']!=20:raise SystemExit('Not all twenty current tasks meet strict calibration')
    (HERE/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n');(HERE/'STATUS.md').write_text(report(result))
    print(json.dumps({key:result[key] for key in ('validated_tasks','strict_calibration_tasks','recorded_cost_all_versions')}))


if __name__=='__main__':main()
