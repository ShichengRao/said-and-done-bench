"""Finish only untouched attempts after the earlier queue ends, under the same $50 cap."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import api_spending
ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--previous-pid',type=int,required=True);args=parser.parse_args()
    while True:
        try:os.kill(args.previous_pid,0)
        except ProcessLookupError:break
        time.sleep(10)
    original=json.loads((ROOT/'heldout7/delivery_validation/opus-output-bounded-remaining.json').read_text())
    for row in original['tasks']:
        run=ROOT/'runs/calibration-h7-delivery'/row['task']/'attempt1-opus-5-5'
        lease=ROOT/'runs/h7-api-budget/leases'/('calibration-'+row['task']+'.json')
        if run.exists() or lease.exists():continue
        # Existing judges finish first. The calibrated model/effort/window/response cap are unchanged;
        # 5-minute cache writes lower the conservative reservation, not the task requirements.
        while True:
            budget=api_spending.snapshot()
            if not any(not j['closed'] for j in budget['jobs']):break
            time.sleep(10)
        cap=min(1.5,int((budget['unreserved_usd']-1.7-.03)*100)/100)
        if cap<.5:
            print(json.dumps({'event':'final_budget_stop','task':row['task'],'available':budget['unreserved_usd']}),flush=True);return
        out=ROOT/'heldout7/delivery_validation'/('final-api-'+row['task']+'.json')
        assert not out.exists()
        data={**original,'tasks':[row],'source_review':'Same frozen validation; previously unstarted attempt only. Five-minute cache billing profile; session cap selected solely from remaining authorized budget.','selected_session_cap_usd':cap}
        out.write_text(json.dumps(data,indent=2)+'\n')
        print(json.dumps({'event':'final_queue_start','task':row['task'],'session_cap_usd':cap}),flush=True)
        code=subprocess.call([str(ROOT/'.venv/bin/python'),str(ROOT/'heldout7/_shared/api_calibrate_cache_bounded.py'),'--validation',str(out),'--session-cap',str(cap)],cwd=ROOT)
        if code:raise SystemExit(code)

if __name__=='__main__':main()
