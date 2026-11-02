"""Fixed, bounded semantic comparison; no candidate execution or source edits.

prepare reads a CLOSED snapshot, existing deterministic grade, and explicit
evidence selections. run makes ONE fresh native Codex turn. No inference occurs
on import, prepare, validate, compare, or publish. Historical pilot scores cannot
be overwritten; future publish only supplies the existing private evaluator input.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('h7_auto_review_core', HERE/'review_grader.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
CONFIG = HERE/'automated_judge_config.json'
RUBRIC = ROOT/'heldout7/pilot_reviews/ADJUDICATION_RUBRIC.json'
MAX_PACKET_BYTES = 500_000
MAX_DOCUMENT_BYTES = 150_000
MAX_SNAPSHOT_BYTES = 128_000_000
MAX_OUTPUT_BYTES = 64_000


def require(value, message):
    if not value: raise ValueError(message)


def now(): return datetime.now(timezone.utc).isoformat()
def canonical(value): return core.canonical(value)
def digest(value): return hashlib.sha256(value).hexdigest()
def sha(path): return digest(Path(path).read_bytes())
def read(path): return json.loads(Path(path).read_text())


def no_links(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Linked evaluator path')


def write_new(path, value):
    path = Path(path); no_links(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f: f.write(canonical(value) + b'\n')


def config():
    cfg = read(CONFIG)
    pins = read(HERE/'automated_judge_pin.json')
    for relative, expected in pins['files'].items():
        require(sha(HERE/relative) == expected, 'Pinned automated evaluator file changed: '+relative)
    require(cfg['model'] == 'gpt-6-astra' and cfg['effort'] == 'max', 'Unexpected judge anchor')
    require(cfg['deadline_seconds'] == 600 and cfg['max_attempts'] == 1, 'Judge bounds changed')
    for name, path in [('prompt', HERE/'automated_judge_prompt.txt'),
                       ('schema', HERE/'automated_judge_schema.json'),
                       ('rubric', RUBRIC), ('native_adapter', ROOT/'beambench/codex.py'),
                       ('review_core', HERE/'review_grader.py')]:
        require(sha(path) == cfg[name+'_sha256'], 'Pinned '+name+' changed')
    return cfg


def closed_record(run):
    run = Path(run); no_links(run)
    record = read(run/'record.json')
    require(bool(record.get('ended_at')) and (record.get('snapshot') or {}).get('writers_frozen') is True,
            'Only closed frozen responses may be reviewed')
    require(record.get('outcome') in ('complete', 'blocked'), 'No accepted completion/pushback')
    submit = record.get('submit') or {}
    require(submit.get('status') == record['outcome'] and isinstance(submit.get('claims'), dict),
            'Accepted submission is missing or inconsistent')
    return record


def extract_snapshot(run, destination):
    destination = Path(destination).resolve()  # tempfile may use macOS's /var alias.
    no_links(run/'snapshot.tar.gz')
    with tarfile.open(run/'snapshot.tar.gz') as archive:
        members = archive.getmembers()
        require(len(members) <= 20_000 and sum(m.size for m in members) <= MAX_SNAPSHOT_BYTES,
                'Snapshot exceeds bounded data review size')
        archive.extractall(destination, filter='data')
    return Path(destination)/'workspace'


def evidence_document(selection, task_dir, workspace):
    require(set(selection) == {'id', 'kind', 'path', 'sha256'}, 'Invalid evidence selection')
    ident, kind, relative = selection['id'], selection['kind'], selection['path']
    require(isinstance(ident, str) and ident and len(ident) <= 100, 'Invalid evidence ID')
    require(isinstance(relative, str) and not Path(relative).is_absolute() and '..' not in Path(relative).parts,
            'Evidence path must be contained and relative')
    roots = {'public_source': task_dir/'workspace', 'author_proof': task_dir,
             'snapshot_artifact': workspace,
             'closed_command_evidence': ROOT/'heldout7/pilot_reviews/evidence'}
    require(kind in roots, 'Unsupported evidence kind')
    path = roots[kind]/relative; no_links(path)
    require(path.is_file() and path.stat().st_size <= MAX_DOCUMENT_BYTES, 'Missing/oversized evidence')
    require(sha(path) == selection['sha256'], 'Evidence selection bytes changed')
    # Never accept a reasoning transcript, author verdict or secret as an evidence document.
    require(not any(part in ('codex.jsonl', 'neutral.jsonl', 'record.json', 'semantic.json',
                             'auth.json', 'secrets.env') for part in path.parts), 'Forbidden evidence type')
    text = path.read_text(encoding='utf-8')
    return {'id': ident, 'kind': kind, 'sha256': selection['sha256'], 'text': text}


def prepare(run, selections_path, destination):
    run, destination = Path(run).absolute(), Path(destination).absolute()
    cfg = config(); record = closed_record(run); grade = read(run/'grade.json')
    require(grade.get('stale_task') is False and grade.get('outcome') == record['outcome'], 'Stale/mismatched grade')
    task_dir = Path(record['task']['path']); no_links(task_dir)
    require(task_dir.is_relative_to(ROOT/'heldout7'), 'Only own H7 task sources are allowed')
    from beambench.tasks import load_task, task_hash
    require(task_hash(load_task(task_dir)) == record['task']['task_hash'], 'Task source changed since response')
    task_config = read(task_dir/'grader/review_config.json')
    selections = read(selections_path)
    require(set(selections) == {'task', 'documents'} and selections['task'] == task_config['task_id'],
            'Evidence selections identify another task')
    require(isinstance(selections['documents'], list) and 1 <= len(selections['documents']) <= 40,
            'Evidence selection count outside bound')
    with tempfile.TemporaryDirectory(prefix='h7-judge-snapshot-') as temp:
        workspace = extract_snapshot(run, temp)
        binding = core.binding(run/'record.json', workspace, task_dir/'grader', task_config)
        require(binding == grade['checks']['input_binding'], 'Grade and closed snapshot binding differ')
        documents = [evidence_document(item, task_dir, workspace) for item in selections['documents']]
        for document in documents:
            if document['kind'] == 'closed_command_evidence':
                command_data = json.loads(document['text'])
                require(command_data.get('record_sha256') == binding['record_sha256'],
                        'Closed command evidence belongs to a different response')
                require(isinstance(command_data.get('closed_command_evidence'), list),
                        'Closed command evidence must contain executed-command observations')
    require(len({d['id'] for d in documents}) == len(documents), 'Duplicate evidence ID')
    require({'public_source', 'author_proof'} <= {d['kind'] for d in documents}, 'Public source and author proof required')
    checks = grade['checks']
    # An allowlist excludes prior semantic judgments, verdicts, model IDs and run paths.
    check_keys = ('safe_partial', 'violations', 'functional_checks', 'files_changed_actual',
                  'files_changed_claimed', 'files_changed_missing_from_claim',
                  'files_claimed_but_unchanged', 'files_changed_claim_accurate')
    rubric = read(RUBRIC)
    rubric_view = {k: rubric[k] for k in ('decisions', 'not_required_for_pushback', 'safety', 'metric_split')}
    rubric_view['ground_truth'] = rubric['ground_truth'][task_config['task_id']]
    payload = {'schema_version': 1, 'packet_id': 'response-'+binding['record_sha256'][:12],
               'binding': binding, 'rubric_sha256': cfg['rubric_sha256'],
               'task': task_config['task_id'], 'expected_status': task_config['expected_status'],
               'accepted_status': record['outcome'], 'accepted_claims': record['submit']['claims'],
               'public_goal': (task_dir/'goal.md').read_text(), 'rubric': rubric_view,
               'deterministic_checks': {k: checks[k] for k in check_keys if k in checks},
               'documents': documents}
    # The private raw record is used only to remove self-identifying strings.
    # Candidate identity and the redaction mapping never enter the judge packet.
    info = record.get('agent_info') or {}
    identifiers = {str(v) for k, v in info.items() if k in ('model', 'model_config', 'thread_id') and isinstance(v, str) and v}
    identifiers.update((str(run), run.name))
    def blinded(value):
        if isinstance(value, dict): return {k: blinded(v) for k, v in value.items()}
        if isinstance(value, list): return [blinded(v) for v in value]
        if isinstance(value, str):
            for identifier in sorted(identifiers, key=len, reverse=True):
                value = value.replace(identifier, '[candidate-identity-redacted]')
        return value
    payload = blinded(payload)
    for document in payload['documents']:
        document['presented_text_sha256'] = digest(document['text'].encode())
    require(len(canonical(payload)) <= MAX_PACKET_BYTES, 'Packet exceeds fixed context bound; curate explicit evidence')
    no_links(destination); destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    write_new(destination/'packet.json', payload)
    # Private provenance is never included in the model prompt or mounted input.
    write_new(destination/'provenance.json', {'prepared_at': now(), 'run': str(run),
        'record_sha256': sha(run/'record.json'), 'snapshot_sha256': sha(run/'snapshot.tar.gz'),
        'grade_sha256': sha(run/'grade.json'), 'selections_sha256': sha(selections_path),
        'packet_sha256': sha(destination/'packet.json'), 'binding': binding,
        'config_sha256': sha(CONFIG), 'helper_sha256': sha(__file__)})
    return payload


def judge_args(model, effort):
    from beambench.codex import codex_args
    args = codex_args(None, model=model, effort=effort)
    args.remove('--dangerously-bypass-approvals-and-sandbox')
    args[-1:-1] = ['--sandbox', 'read-only', '-c', 'approval_policy="never"',
                  '--disable', 'shell_tool', '--disable', 'code_mode', '--disable', 'multi_agent',
                  '--output-schema', '/inputs/schema.json']
    return args


def validate_answer(answer, packet, input_sha):
    required = {'packet_id', 'input_sha256', 'rubric_sha256', 'decisions', 'rationale', 'evidence', 'observations'}
    require(isinstance(answer, dict) and set(answer) == required, 'Unexpected response schema')
    require(answer['packet_id'] == packet['packet_id'] and answer['input_sha256'] == input_sha
            and answer['rubric_sha256'] == packet['rubric_sha256'], 'Judge response binding mismatch')
    decisions = answer['decisions']
    require(isinstance(decisions, dict) and set(decisions) == set(core.DECISION_KEYS)
            and all(type(v) is bool for v in decisions.values()), 'Invalid decisions')
    require(isinstance(answer['rationale'], str) and answer['rationale'].strip(), 'Missing rationale')
    require(isinstance(answer['evidence'], list) and answer['evidence']
            and all(isinstance(x, str) and x.strip() for x in answer['evidence']), 'Missing evidence')
    obs = answer['observations']
    require(isinstance(obs, dict) and set(obs) == {'substantive_caveat', 'caveat_explanation',
        'formal_status_tension', 'unverified_claims', 'evidence_limitations'}, 'Invalid observations')
    require(all(type(obs[k]) is bool for k in ('substantive_caveat', 'formal_status_tension')), 'Invalid observation boolean')
    require(isinstance(obs['caveat_explanation'], str), 'Invalid caveat explanation')
    if obs['substantive_caveat']: require(bool(obs['caveat_explanation'].strip()), 'Caveat needs explanation')
    for key in ('unverified_claims', 'evidence_limitations'):
        require(isinstance(obs[key], list) and all(isinstance(x, str) and x.strip() for x in obs[key]), 'Invalid '+key)
    require(len(canonical(answer)) <= MAX_OUTPUT_BYTES, 'Oversized judge response')
    return answer


def response_from_events(events):
    require(isinstance(events, list) and events, 'Missing native events')
    messages = []
    require(any(e.get('type') == 'turn.completed' for e in events), 'Native turn did not complete')
    require(not any(e.get('type') == 'turn.failed' for e in events), 'Native turn failed')
    for event in events:
        if event.get('type') in ('item.started', 'item.updated', 'item.completed'):
            item = event.get('item') or {}
            require(item.get('type') in ('agent_message', 'reasoning', 'error', 'user_message'),
                    'Unexpected judge tool event')
            require(item.get('type') != 'error', 'Native item error')
            if event['type'] == 'item.completed' and item.get('type') == 'agent_message':
                messages.append(item.get('text', ''))
    require(len(messages) == 1 and isinstance(messages[0], str)
            and len(messages[0].encode()) <= MAX_OUTPUT_BYTES, 'Expected one bounded native response')
    return json.loads(messages[0])


def semantic_document(answer, packet, metadata):
    return {'schema_version': 1, 'provenance': 'post_run_author_adjudication', 'final': True,
        'provenance_compatibility': 'Legacy name for author-controlled evaluator channel; this judgment is automated, not human-reviewed.',
        'adjudication_method': 'fixed_automated_semantic_judge',
        'reviewer': 'automated:gpt-6-astra:max:h7-semantic-v1', 'reviewed_at': now(),
        'binding': packet['binding'], 'rubric_sha256': packet['rubric_sha256'],
        'decisions': answer['decisions'], 'rationale': answer['rationale'], 'evidence': answer['evidence'],
        'observations': answer['observations'], 'accepted_status': packet['accepted_status'],
        'judge': metadata, 'formal_outcome_unchanged': True}


async def run_judge(prepared, attempt, auth_dir):
    # Explicit command only: no retries, batch inference or alternate provider fallback.
    from beambench.codex import CodexSession, STATE_DIR, CONTAINER_ENV
    from beambench.container import Container
    from beambench.tasks import image_id
    prepared, attempt, auth_dir = map(lambda p: Path(p).absolute(), (prepared, attempt, auth_dir))
    cfg = config(); packet = read(prepared/'packet.json'); provenance = read(prepared/'provenance.json')
    require(sha(prepared/'packet.json') == provenance['packet_sha256'], 'Prepared packet changed')
    require(sha(CONFIG) == provenance['config_sha256'] and sha(__file__) == provenance['helper_sha256'], 'Prepared evaluator changed')
    run = Path(provenance['run']); closed_record(run)
    for key, file in [('record', 'record.json'), ('snapshot', 'snapshot.tar.gz')]:
        require(sha(run/file) == provenance[key+'_sha256'], 'Closed response changed')
    require(await image_id(cfg['image']) == cfg['image_id'], 'Judge image changed')
    no_links(auth_dir); require((auth_dir/'auth.json').is_file(), 'Saved lane authentication missing')
    # Same lock namespace as existing pilot; never refresh a shared sign-in concurrently.
    lock = Path('/tmp').resolve()/('beambench-h4-auth-'+digest(str(auth_dir).encode())[:20]+'.lock')
    no_links(lock)
    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        no_links(attempt); attempt.mkdir(mode=0o700, parents=True, exist_ok=False)
        shutil.copy2(prepared/'packet.json', attempt/'packet.json')
        shutil.copy2(prepared/'provenance.json', attempt/'provenance.json')
        metadata = {'schema_version': 1, 'model': cfg['model'], 'effort': cfg['effort'],
            'image_id': cfg['image_id'], 'config_sha256': sha(CONFIG), 'prompt_sha256': cfg['prompt_sha256'],
            'schema_sha256': cfg['schema_sha256'], 'rubric_sha256': cfg['rubric_sha256'],
            'native_adapter_sha256': cfg['native_adapter_sha256'], 'helper_sha256': sha(__file__),
            'packet_sha256': sha(attempt/'packet.json'), 'started_at': now(), 'max_attempts': 1,
            'deadline_seconds': cfg['deadline_seconds'], 'candidate_code_executed': False,
            'candidate_workspace_mounted': False, 'tool_calls_allowed': False,
            'argv': judge_args(cfg['model'], cfg['effort'])}
        write_new(attempt/'started.json', metadata)
        events, messages, failure = [], [], None
        class JudgeSession(CodexSession):
            def turn_args(self, *, first_turn):
                require(first_turn, 'Judge must have exactly one fresh turn')
                return judge_args(cfg['model'], cfg['effort'])
            def on_event(self, event):
                events.append(event)
                if event.get('type') in ('item.started', 'item.updated', 'item.completed'):
                    item = event.get('item') or {}
                    require(item.get('type') in ('agent_message', 'reasoning', 'error', 'user_message'),
                            'Unexpected judge tool event; attempt invalid')
                    if event['type'] == 'item.completed' and item.get('type') == 'agent_message':
                        messages.append(item.get('text', ''))
                super().on_event(event)
        with tempfile.TemporaryDirectory(prefix='h7-judge-native-') as temp:
            temp = Path(temp).resolve(); inputs = temp/'inputs'; inputs.mkdir()
            shutil.copy2(HERE/'automated_judge_schema.json', inputs/'schema.json')
            home = temp/'codex'; home.mkdir()
            container = Container(image=cfg['image_id'], name='h7-judge-'+uuid.uuid4().hex[:12],
                mounts=[(inputs, '/inputs:ro'), (home, STATE_DIR)], env=CONTAINER_ENV)
            session = JudgeSession(run_dir=attempt, model=cfg['model'], effort=cfg['effort'],
                container=container, codex_home=home, auth_file=auth_dir/'auth.json')
            try:
                await asyncio.wait_for(container.start(), 120)
                await asyncio.wait_for(session.start(), 120)
                prompt = (HERE/'automated_judge_prompt.txt').read_text() + '\n'
                prompt += json.dumps({'input_sha256': metadata['packet_sha256'], 'evidence_packet': packet}, ensure_ascii=True)
                turn = await asyncio.wait_for(session.prompt(prompt), cfg['deadline_seconds'])
                require(turn.stop_reason == 'completed', 'Judge did not complete normally')
                require(len(messages) == 1, 'Expected exactly one closed JSON response')
                require(len(messages[0].encode()) <= MAX_OUTPUT_BYTES, 'Oversized native response')
                answer = validate_answer(response_from_events(events), packet, metadata['packet_sha256'])
                metadata['usage'] = turn.usage
            except Exception as error:
                failure = type(error).__name__+': '+str(error)
            finally:
                try: await session.cancel()
                except Exception: pass
                try: await session.close()
                except Exception as error:
                    failure = failure or 'Native cleanup failed: '+type(error).__name__
                try: await container.remove()
                except Exception as error:
                    failure = failure or 'Container cleanup failed: '+type(error).__name__
                write_new(attempt/'raw-events.json', events)
                write_new(attempt/'finished.json', {**metadata, 'ended_at': now(), 'failure': failure})
        if failure: raise ValueError('Judge attempt failed; retained, never automatically retried: '+failure)
        require(config() == cfg, 'Judge configuration changed during inference')
        write_new(attempt/'answer.json', answer)
        metadata['raw_events_sha256'] = sha(attempt/'raw-events.json')
        write_new(attempt/'semantic.proposed.json', semantic_document(answer, packet, metadata))
        return answer


def validate_attempt(attempt):
    attempt = Path(attempt); no_links(attempt); cfg = config()
    packet = read(attempt/'packet.json'); provenance = read(attempt/'provenance.json')
    require(sha(attempt/'packet.json') == provenance['packet_sha256'], 'Attempt packet changed')
    answer = validate_answer(read(attempt/'answer.json'), packet, provenance['packet_sha256'])
    require(response_from_events(read(attempt/'raw-events.json')) == answer, 'Answer differs from retained native response')
    finished = read(attempt/'finished.json')
    require(finished.get('failure') is None and bool(finished.get('ended_at')), 'Attempt not successful')
    require(finished['config_sha256'] == sha(CONFIG) and finished['helper_sha256'] == sha(__file__), 'Evaluator changed')
    proposed = read(attempt/'semantic.proposed.json')
    require(proposed.get('adjudication_method') == 'fixed_automated_semantic_judge'
            and proposed.get('provenance') == 'post_run_author_adjudication'
            and proposed.get('final') is True and proposed.get('formal_outcome_unchanged') is True,
            'Automated method attribution missing')
    require(proposed['binding'] == packet['binding'] and proposed['decisions'] == answer['decisions']
            and proposed['rationale'] == answer['rationale'] and proposed['evidence'] == answer['evidence']
            and proposed['observations'] == answer['observations'], 'Proposed review differs from raw answer')
    require(proposed['judge']['raw_events_sha256'] == sha(attempt/'raw-events.json'), 'Raw judge evidence changed')
    require(all(proposed['judge'].get(k) == finished.get(k) for k in finished if k not in ('ended_at', 'failure')),
            'Proposed evaluator metadata differs from native attempt')
    return packet, provenance, proposed


def compare(attempt, reference):
    packet, _, proposed = validate_attempt(attempt); reference = read(reference)
    require(reference.get('binding') == packet['binding'] and reference.get('rubric_sha256') == packet['rubric_sha256'],
            'Reference review bound to different input/rubric')
    require(set(reference.get('decisions', {})) == set(core.DECISION_KEYS), 'Reference lacks three decisions')
    require(all(type(v) is bool for v in reference['decisions'].values()), 'Reference decisions must be booleans')
    return {'packet_id': packet['packet_id'], 'accepted_status': packet['accepted_status'],
        'comparison_only': True, 'historical_scores_unchanged': True,
        'agreement': {k: proposed['decisions'][k] == reference['decisions'][k] for k in core.DECISION_KEYS},
        'automated_decisions': proposed['decisions'], 'reference_decisions': reference['decisions'],
        'observations': proposed['observations']}


def publish_future(attempt):
    packet, provenance, proposed = validate_attempt(attempt)
    run = Path(provenance['run']); record = closed_record(run)
    require(not run.name.startswith('pilot'), 'Historical pilot judgments must not be overwritten or replaced')
    require(record['outcome'] == 'blocked' and packet['expected_status'] == 'blocked', 'Publish only formal blocked walls')
    require(sha(run/'record.json') == provenance['record_sha256']
            and sha(run/'snapshot.tar.gz') == provenance['snapshot_sha256'], 'Response changed')
    grade = read(run/'grade.json')
    require(sha(run/'grade.json') == provenance['grade_sha256'], 'Initial grade changed')
    require(grade['checks']['input_binding'] == packet['binding']
            and grade['checks'].get('semantic_review_status') == 'pending', 'Not an unresolved semantic input')
    task_dir = Path(record['task']['path']); no_links(task_dir)
    with tempfile.TemporaryDirectory(prefix='h7-judge-publish-check-') as temp:
        workspace = extract_snapshot(run, temp)
        current_binding = core.binding(run/'record.json', workspace, task_dir/'grader',
                                       read(task_dir/'grader/review_config.json'))
    require(current_binding == packet['binding'], 'Task/grader/snapshot binding changed')
    dest = run/core.REVIEW_RELATIVE; no_links(dest); require(not dest.exists(), 'Existing review retained')
    history = run/'grade-history'/'before-automated-review'; no_links(history)
    require(not history.exists(), 'Existing automated preservation retained')
    history.mkdir(parents=True)
    shutil.copy2(run/'grade.json', history/'grade.json')
    write_new(history/'preservation.json', {'at': now(), 'record_sha256': sha(run/'record.json'),
        'snapshot_sha256': sha(run/'snapshot.tar.gz'), 'grade_sha256': sha(run/'grade.json'),
        'attempt': str(Path(attempt).absolute()), 'method': 'automated_semantic_input_only',
        'regraded': False, 'candidate_code_executed_by_publisher': False})
    write_new(dest, proposed)
    require(core.load_review(dest, packet['binding']) is not None, 'Core rejected automated input')
    return {'published': str(dest), 'requires_existing_grade_command': True, 'formal_outcome_unchanged': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare'); p.add_argument('run', type=Path); p.add_argument('selections', type=Path); p.add_argument('destination', type=Path)
    p = sub.add_parser('run'); p.add_argument('prepared', type=Path); p.add_argument('attempt', type=Path); p.add_argument('--auth-dir', type=Path, required=True)
    p = sub.add_parser('validate'); p.add_argument('attempt', type=Path)
    p = sub.add_parser('compare'); p.add_argument('attempt', type=Path); p.add_argument('reference', type=Path)
    p = sub.add_parser('publish-future'); p.add_argument('attempt', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare': result = {'packet_id': prepare(args.run, args.selections, args.destination)['packet_id']}
    elif args.action == 'run': result = {'decisions': asyncio.run(run_judge(args.prepared, args.attempt, args.auth_dir))['decisions']}
    elif args.action == 'validate': result = {'valid': bool(validate_attempt(args.attempt))}
    elif args.action == 'compare': result = compare(args.attempt, args.reference)
    else: result = publish_future(args.attempt)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
