"""One stateless, tool-free API judgment of an explicitly prepared evidence packet.

Reuses the frozen rubric, prompt, output schema and answer validator. Historical
pilot grades are never modified. API transport/model changes are versioned.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import httpx

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from api_author import api_key
import api_spending

spec = importlib.util.spec_from_file_location('frozen_h7_judge', HERE/'automated_judge.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):
    with Path(path).open('x') as file: json.dump(value, file, indent=2); file.write('\n')


def config():
    cfg = json.loads((HERE/'api_judge_config.json').read_text())
    for name, digest in cfg['files'].items():
        assert sha(HERE/name) == digest, 'API judge source changed: '+name
    assert cfg['model'] == 'claude-opus-5-5' and cfg['max_attempts'] == 1
    return cfg


def run(packet_path, destination):
    cfg = config()
    packet_path, destination = Path(packet_path).resolve(), Path(destination).resolve()
    assert packet_path.is_relative_to(ROOT/'heldout7')
    assert destination.is_relative_to(ROOT/'heldout7')
    assert not destination.exists(), 'Never overwrite or automatically reroll a judgment'
    packet = json.loads(packet_path.read_text())
    packet_sha = sha(packet_path)
    system = (HERE/'automated_judge_prompt.txt').read_text()
    content = json.dumps({'input_sha256':packet_sha,'evidence_packet':packet},ensure_ascii=True)
    schema = json.loads((HERE/'automated_judge_schema.json').read_text())
    body = {'model':cfg['model'],'max_tokens':cfg['max_tokens'],
        'system':system,'messages':[{'role':'user','content':content}],
        'output_config':{'effort':cfg['effort'],'format':{'type':'json_schema','schema':schema}}}
    # UTF-8 byte count is a conservative token bound for these text-only inputs.
    upper_cost = (len(json.dumps(body).encode())*4 + cfg['max_tokens']*20)/1_000_000 + .10
    assert len(content.encode()) <= 500_000
    ledger = ROOT/'runs/h7-api-budget'
    leases = ledger/'leases'
    leases.mkdir(parents=True,exist_ok=True)
    ident = 'judge-'+packet['packet_id']
    log = ledger/(ident+'.jsonl')
    with (ledger/'allocation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        budget = api_spending.snapshot()
        assert budget['unreserved_usd'] >= upper_cost, 'Insufficient unreserved API budget'
        assert sum(not j['closed'] for j in budget['jobs']) < 3, 'Three Opus jobs already active'
        # This is one bounded request, not an agent loop; upper_cost includes its full input/output.
        write(leases/(ident+'.json'),{'job':ident,'limit_usd':upper_cost,'inflight_reserve_usd':0,
                                    'log':str(log.relative_to(ROOT))})
        destination.mkdir(parents=True)
    shutil.copy2(packet_path,destination/'packet.json')
    metadata = {'judge_id':cfg['judge_id'],'model':cfg['model'],'effort':cfg['effort'],
        'transport':'Anthropic Messages API','started_at':now(),'max_attempts':1,
        'packet_sha256':packet_sha,'config_sha256':sha(HERE/'api_judge_config.json'),
        'tool_calls_allowed':False,'candidate_code_executed':False,
        'candidate_workspace_mounted':False,'reserved_request_cost_usd':upper_cost}
    write(destination/'started.json',metadata)
    try:
        response = httpx.post('https://api.anthropic.com/v1/messages',json=body,
            headers={'x-api-key':api_key(),'anthropic-version':'2023-06-01'},timeout=600)
        raw = response.json()
        write(destination/'raw-response.json',raw)
        response.raise_for_status()
        assert raw.get('model') == cfg['model']
        assert raw.get('stop_reason') == 'end_turn'
        assert all(b['type'] in ('thinking','redacted_thinking','text') for b in raw['content'])
        texts = [b['text'] for b in raw['content'] if b['type']=='text']
        assert len(texts)==1
        with log.open('x') as file:
            file.write(json.dumps({'type':'assistant','message':raw})+'\n')
        cost = api_spending.log_cost(log)['cost_usd']
        with log.open('a') as file:
            file.write(json.dumps({'type':'result','total_cost_usd':cost})+'\n')
        answer = engine.validate_answer(json.loads(texts[0]),packet,packet_sha)
        write(destination/'answer.json',answer)
        reasons = engine.abstention(answer)
        metadata.update(ended_at=now(),recorded_cost_usd=cost,usage=raw.get('usage'),
                        response_sha256=sha(destination/'raw-response.json'),valid=True)
        semantic = {'schema_version':1,'provenance':'post_run_author_adjudication',
            'provenance_compatibility':'Legacy private evaluator channel; this judgment is automated.',
            'adjudication_method':'fixed_automated_semantic_judge',
            'final':not reasons,'abstained':bool(reasons),'abstention_reasons':reasons,
            'publishable':not reasons and packet['accepted_status']==packet['expected_status']=='blocked',
            'reviewer':'automated:'+cfg['model']+':'+cfg['effort']+':'+cfg['judge_id'],
            'reviewed_at':now(),'binding':packet['binding'],'rubric_sha256':packet['rubric_sha256'],
            'decisions':answer['decisions'],'rationale':answer['rationale'],'evidence':answer['evidence'],
            'observations':answer['observations'],'accepted_status':packet['accepted_status'],
            'judge':metadata,'formal_outcome_unchanged':True}
        write(destination/'semantic.proposed.json',semantic)
        write(destination/'finished.json',metadata)
        print(json.dumps({'packet_id':packet['packet_id'],'valid':True,'abstained':bool(reasons),
                          'cost_usd':cost,'decisions':answer['decisions']}),flush=True)
    except Exception as error:
        write(destination/'failed.json',{'at':now(),'error_type':type(error).__name__,
            'retry_performed':False,'usage_status':'Retain budget reservation when final usage is unavailable.'})
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('packet',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    run(args.packet,args.destination)
