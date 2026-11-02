"""Apply resolved author reviews without rerunning inference or altering raw evidence.

Input is one recorded independent+primary resolution per anonymized packet.
The static grader remains unchanged. Initial grading artifacts are preserved.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from beambench.tasks import load_task, task_hash, grader_hash
spec = importlib.util.spec_from_file_location('review_core', Path(__file__).with_name('review_grader.py'))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
H = ROOT / 'heldout7'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def now(): return datetime.now(timezone.utc).isoformat()
def write_new(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f: f.write(json.dumps(value, indent=2) + '\n')

def no_links(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Linked evaluator path: ' + str(path))

def validate_resolution(item, packet, rubric_sha):
    if item.get('packet_id') != packet['packet_id']:
        raise ValueError('Resolution packet identity mismatch')
    if item.get('binding') != packet['binding'] or item.get('rubric_sha256') != rubric_sha:
        raise ValueError('Resolution binding/rubric mismatch')
    decisions = item.get('decisions')
    if not isinstance(decisions, dict) or set(decisions) != set(core.DECISION_KEYS):
        raise ValueError('Wrong decisions')
    if any(type(decisions[k]) is not bool for k in core.DECISION_KEYS):
        raise ValueError('Non-boolean decision')
    for key in ('reviewer', 'rationale', 'independent_review_file', 'independent_review_sha256'):
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise ValueError('Missing ' + key)
    if not isinstance(item.get('evidence'), list) or not item['evidence'] or not all(isinstance(e, str) and e.strip() for e in item['evidence']):
        raise ValueError('Missing evidence')
    peer = ROOT / item['independent_review_file']
    if sha(peer) != item['independent_review_sha256']:
        raise ValueError('Independent review changed')
    if item.get('primary_reviewed') is not True or 'disagreements' not in item:
        raise ValueError('Primary review/resolution missing')
    peer_items = read(peer)['reviews']
    matches = [p for p in peer_items if p.get('packet_id') == item['packet_id']]
    if len(matches) != 1:
        raise ValueError('Independent review does not identify exactly one packet')
    independent = matches[0]
    if independent.get('binding') != packet['binding'] or independent.get('rubric_sha256') != rubric_sha:
        raise ValueError('Independent review binding/rubric mismatch')
    if any(not isinstance(independent.get(k), str) or not independent[k].strip() for k in ('reviewer','rationale')):
        raise ValueError('Independent review lacks attribution/evidence')
    if (not isinstance(independent.get('evidence'), list) or not independent['evidence']
        or not all(isinstance(e, str) and e.strip() for e in independent['evidence'])):
        raise ValueError('Independent review lacks evidence')
    peer_decisions = independent.get('decisions')
    if not isinstance(peer_decisions, dict) or set(peer_decisions) != set(core.DECISION_KEYS):
        raise ValueError('Independent review lacks decisions')
    if any(type(peer_decisions[k]) is not bool for k in core.DECISION_KEYS):
        raise ValueError('Independent review has non-boolean decisions')
    differences = {k for k in core.DECISION_KEYS if peer_decisions[k] != decisions[k]}
    disagreements = item['disagreements']
    if not isinstance(disagreements, list) or len(disagreements) != len(differences):
        raise ValueError('Independent disagreements not resolved')
    if {d.get('decision') for d in disagreements} != differences:
        raise ValueError('Disagreement keys do not match actual differences')
    for d in disagreements:
        key = d['decision']
        if (d.get('independent') is not peer_decisions[key] or d.get('primary') is not decisions[key]
            or not isinstance(d.get('resolution'), str) or not d['resolution'].strip()):
            raise ValueError('Unreasoned disagreement resolution')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resolutions', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    lock_path = ROOT/'runs/calibration-h7/control/pilot.lock'
    no_links(lock_path)
    lock = lock_path.open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    resolutions = read(args.resolutions)
    mapping = read(H/'pilot_reviews/PACKET_MAPPING.json')['packets']
    events = [json.loads(line) for line in (ROOT/'runs/calibration-h7/control/events.jsonl').read_text().splitlines()]
    assert any(e.get('event') == 'pilot_finished' for e in events), 'Wait for closed pilot'
    rubric_sha = sha(H/'pilot_reviews/ADJUDICATION_RUBRIC.json')
    approval = read(H/'pilot_reviews/SOURCE_REVIEW.json')
    assert approval['rubric_sha256'] == rubric_sha
    by_id = {r['packet_id']: r for r in resolutions['reviews']}
    assert len(by_id) == len(resolutions['reviews']) and set(by_id) == {m['packet_id'] for m in mapping}
    plans = []
    for m in mapping:
        packet = read(m['packet']); assert sha(m['packet']) == m['packet_sha256']
        assert packet['packet_id'] == m['packet_id'] and packet['binding'] == m['binding']
        assert packet['rubric_sha256'] == m['rubric_sha256'] == rubric_sha
        item = by_id[m['packet_id']]; validate_resolution(item, packet, rubric_sha)
        run = ROOT/m['run']; record = read(run/'record.json'); task = load_task(Path(record['task']['path']))
        assert record['ended_at'] and record['outcome'] == 'blocked' and record['snapshot']['writers_frozen']
        start = next(e for e in events if e.get('event') == 'start' and e['run'] == m['run'])
        assert start['runtime_sha256']['heldout7/pilot_reviews/ADJUDICATION_RUBRIC.json'] == rubric_sha
        assert start['runtime_sha256']['heldout7/_shared/review_grader.py'] == sha(H/'_shared/review_grader.py')
        assert task_hash(task) == start['source']['task_hash'] and grader_hash(task) == start['source']['grader_hash']
        assert sha(run/'record.json') == m['binding']['record_sha256'] and sha(run/'snapshot.tar.gz') == m['snapshot_sha256']
        config = read(task.path/'grader/review_config.json')
        assert core.binding(run/'record.json', Path(packet['workspace']), task.path/'grader', config) == m['binding']
        grade = read(run/'grade.json')
        assert grade['checks']['input_binding'] == m['binding'] and grade['checks']['semantic_review_status'] == 'pending'
        assert grade['scored'] is False and grade['verified_success'] is None
        dest = run/core.REVIEW_RELATIVE; history = run/'grade-history'/'before-author-review'
        outputs = [dest, history, history.parent/'after-author-review.json',
                   history.parent/'resolved-review-event.json', history.parent/'author-review-grade.log']
        for output in outputs:
            no_links(output)
            assert not output.exists(), 'Preserve existing resolution; do not overwrite'
        review = {'schema_version':1, 'provenance':'post_run_author_adjudication', 'final':True,
                  'reviewer':item['reviewer'], 'reviewed_at':now(), 'binding':m['binding'],
                  'decisions':item['decisions'], 'rationale':item['rationale'], 'evidence':item['evidence'],
                  'rubric_sha256':rubric_sha, 'resolution_file':str(args.resolutions.resolve()),
                  'resolution_sha256':sha(args.resolutions), 'independent_review_file':item['independent_review_file'],
                  'independent_review_sha256':item['independent_review_sha256'], 'disagreements':item['disagreements']}
        plans.append((m, run, dest, history, review, start['source']['grader_hash']))
    if not args.apply:
        print(json.dumps({'validated_reviews':len(plans), 'apply':False})); return
    for m, run, dest, history, review, gh in plans:
        history.mkdir(parents=True)
        shutil.copy2(run/'grade.json', history/'grade.json')
        if (run/'grading').exists(): shutil.copytree(run/'grading', history/'grading', symlinks=True)
        write_new(history/'preservation.json', {'at':now(), 'reason':'Pending semantic input resolved, no new inference',
            'record_sha256':sha(run/'record.json'), 'snapshot_sha256':sha(run/'snapshot.tar.gz'),
            'grade_sha256':sha(run/'grade.json'), 'grader_hash':gh,
            'grading_workspace_sha256':core.workspace_digest(run/'grading/workspace')})
        write_new(dest, review)
        assert core.load_review(dest, m['binding']) is not None
        with (history.parent/'author-review-grade.log').open('xb') as log:
            result = subprocess.run([str(ROOT/'.venv/bin/python'), '-m', 'beambench', 'grade', str(run)],
                cwd=ROOT, env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}, stdout=log, stderr=subprocess.STDOUT)
        assert result.returncode == 0, 'Resolved grading failed; preserve evidence and inspect'
        after = read(run/'grade.json')
        assert after['grader_hash'] == gh and after['stale_task'] is False
        assert after['checks']['input_binding'] == m['binding'] and after['checks']['semantic_review_status'] == 'final'
        assert after['checks']['semantic_review_sha256'] == sha(dest) and after['scored'] is True
        assert sha(run/'record.json') == m['binding']['record_sha256'] and sha(run/'snapshot.tar.gz') == m['snapshot_sha256']
        shutil.copy2(run/'grade.json', history.parent/'after-author-review.json')
        write_new(history.parent/'resolved-review-event.json', {'at':now(), 'run':m['run'],
            'record_sha256':sha(run/'record.json'), 'snapshot_sha256':sha(run/'snapshot.tar.gz'),
            'review_sha256':sha(dest), 'before_grade_sha256':sha(history/'grade.json'),
            'after_grade_sha256':sha(run/'grade.json'), 'grader_hash':gh, 'model_inference_repeated':False})
        print(json.dumps({'run':m['run'], 'verified_success':after['verified_success'],
                          'claims_truthful':after.get('claims_truthful'), 'said_and_done':after.get('said_and_done')}),flush=True)

if __name__ == '__main__': main()
