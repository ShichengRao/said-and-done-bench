"""Review newly closed justified-pushback candidates once; never reroll a judge."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import time

import api_judge
import api_spending
import delivery_review

ROOT=api_judge.ROOT
RUNS=ROOT/'runs/calibration-h7-delivery'
OUT=ROOT/'heldout7/delivery_reviews'


def emit(value):
    event={'at':datetime.now(timezone.utc).isoformat(),**value}
    with (OUT/'queue-events.jsonl').open('a') as file:file.write(json.dumps(event)+'\n')
    print(json.dumps(event),flush=True)


def main():
    handled=set()
    while True:
        closed=list(RUNS.glob('h7-*/*/record.json'))
        for record_path in sorted(closed):
            run=record_path.parent
            if run in handled or not (run/'grade.json').exists():continue
            record=json.loads(record_path.read_text());grade=json.loads((run/'grade.json').read_text())
            if not record.get('ended_at') or record.get('outcome')!='blocked':continue
            if (grade.get('checks') or {}).get('semantic_review_status')!='pending':continue
            if sum(not j['closed'] for j in api_spending.snapshot()['jobs'])>=3:continue
            packet_id='response-'+api_judge.sha(record_path)[:12]
            base=OUT/'responses'/packet_id;prepared=base/'prepared';attempt=base/'attempt1-api'
            if attempt.exists():
                handled.add(run);emit({'event':'existing_attempt_needs_attention','run':str(run.relative_to(ROOT))});continue
            if not prepared.exists():delivery_review.prepare(run)
            try:
                api_judge.run(prepared/'packet.json',attempt)
            except AssertionError as error:
                # Allocation races occur before a lease, destination or API call exists.
                if not attempt.exists() and not (ROOT/'runs/h7-api-budget/leases'/('judge-'+packet_id+'.json')).exists():
                    continue
                handled.add(run);emit({'event':'judge_failed','run':str(run.relative_to(ROOT)),'type':type(error).__name__});continue
            except Exception as error:
                handled.add(run);emit({'event':'judge_failed','run':str(run.relative_to(ROOT)),'type':type(error).__name__});continue
            handled.add(run)
            review=json.loads((attempt/'semantic.proposed.json').read_text())
            if not review['publishable']:
                emit({'event':'abstention','run':str(run.relative_to(ROOT)),'reasons':review['abstention_reasons']});continue
            delivery_review.publish(prepared,attempt)
            with (base/'regrade.log').open('x') as log:
                code=subprocess.call([str(ROOT/'.venv/bin/python'),'-m','beambench','grade',str(run)],
                                     cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            grade=json.loads((run/'grade.json').read_text())
            emit({'event':'reviewed','task':record['task']['id'],'run':str(run.relative_to(ROOT)),
                'verified_success':grade.get('verified_success'),'scored':grade.get('scored'),'exit_code':code})
        if len(closed)==40 and all(json.loads(p.read_text()).get('ended_at') for p in closed):
            unresolved=[p for p in closed if (p.parent/'grade.json').exists()
                and (json.loads((p.parent/'grade.json').read_text()).get('checks') or {}).get('semantic_review_status')=='pending'
                and p.parent not in handled]
            if not unresolved:
                emit({'event':'queue_finished','closed_runs':40});return
        time.sleep(10)


if __name__=='__main__':main()
