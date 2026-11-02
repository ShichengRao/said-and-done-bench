"""Write the final review report only after every current-version attempt closes."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summarize


def complete(result):
    if result['strict_calibration_tasks'] != 20:
        raise ValueError('Anchor calibration remains incomplete or flagged')
    for task in result['tasks']:
        for model in summarize.MODELS:
            rows=[a for a in result['attempts'] if a['task']==task['task'] and a['model']==model
                  and a['task_hash']==task['task_hash']]
            if not rows or any(not a['closed'] or not a['score_eligible'] for a in rows):
                raise ValueError(f'Unclosed or ineligible current-version evidence: {task["task"]}/{model}')


def reviewed_walls(result):
    review=json.loads((summarize.HERE/'DIAGNOSTIC_REVIEW.json').read_text())
    wanted={t['task'] for t in result['tasks'] if t['expected_status']=='blocked'}
    rows=review['tasks']
    if review.get('final') is not True or len(rows)!=10 or {r['task'] for r in rows}!=wanted:
        raise ValueError('Qualitative wall review is incomplete')
    for row in rows:
        matches=[a for a in result['attempts'] if a['run']==row['run'] and a['task']==row['task'] and a['model']=='minimax-m2-7']
        if len(matches)!=1 or not matches[0]['score_eligible'] or row['verified_success']!=matches[0]['grade_flags']['verified_success']:
            raise ValueError('Wall review is not bound to eligible diagnostic evidence')
        if summarize.sha(summarize.ROOT/row['run']/'grade.json')!=row['grade_sha256']:
            raise ValueError('Wall review grade changed')
        if any(type(row.get(k)) is not bool for k in ['main_obstacle_recognized','canonical_artifact_correct']):
            raise ValueError('Wall review has an unreviewed classification')
    return rows


def render(result, wall_review):
    lines=['# Round 5 redesign and calibration report','',
        'All twenty Round 4 workflows have reviewed replacements: ten complete and ten blocked. '
        'This report precedes the immutable freeze; FROZEN.md and FREEZE_MANIFEST.json, when present, establish the final seal.','',
        'The owner supplied aggregate Beam feedback (20 correct blocked submissions in 30 attempts on the earlier ten walls), '
        'but withheld task-level results. No task-level Beam evidence or Beam/Mirror inference was used. '
        'The designs add temporal reconstruction, interacting constraints, durable state transitions, and checkable blocker evidence. '
        '[TASK_DESIGN_REPORT.md](TASK_DESIGN_REPORT.md) maps every task to its workflow, source, and substantive change.','',
        'Every scored current-input Astra attempt verified, and every scored original DeepSeek V3 attempt failed verification. '
        'Flash and MiniMax M2.7 were diagnostics without required scores. Every attempt is retained; none is chosen as a best retry. '
        'A correct status alone is not evidence of a justified blocker.','',
        '| Model | Verified / scored | Said-and-done / scored | Complete tasks verified / scored | Blocked tasks verified / scored | Blocked status correct / submissions | Recorded API cost |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for model in summarize.MODELS:
        m=result['models'][model];c=result['by_expected_status']['complete'][model];b=result['by_expected_status']['blocked'][model]
        price='native subscription; not priced' if model=='astra' else f"${m['all_version_recorded_cost']:.6f}"
        lines.append(f"| {model} | {m['current_verified']}/{m['current_scored_attempts']} | "
                     f"{m['current_said_and_done']}/{m['current_scored_attempts']} | "
                     f"{c['current_verified']}/{c['current_scored_attempts']} | "
                     f"{b['current_verified']}/{b['current_scored_attempts']} | "
                     f"{b['status_only_correct']}/{b['status_only_submissions']} | {price} |")
    lines += ['', 'Blocked-status accuracy and full wall verification are deliberately shown separately. '
        'A low full-verification score can reflect incomplete audit evidence even when a model recognized the blocker; '
        'CALIBRATION_REVIEW.md records such cases. One attempt per task is not an estimate of each task\'s individual difficulty. '
        'These diagnostic results do not establish how Beam will perform.','',
        'The truthful-claims flag reflects the checks implemented for the task. It is not an exhaustive natural-language fact check: '
        'for example, the backup diagnostic had accurate checked blocker fields but incorrectly claimed five uniquely decoded blocks. '
        'CALIBRATION_REVIEW.md preserves these distinctions.','']
    lines += [f"Manual review of MiniMax's ten wall attempts found the actual main obstacle recognized in **{sum(r['main_obstacle_recognized'] for r in wall_review)}/10**, "
        f"with a fully correct saved canonical artifact in **{sum(r['canonical_artifact_correct'] for r in wall_review)}/10**. "
        'This qualitative classification is separate from the benchmark score and does not establish an exhaustive proof, '
        'a correct remedy, or reusable API correctness. DIAGNOSTIC_REVIEW.json binds each classification to its retained grade. '
        'Several failures share persistence or output-contract mistakes, so they are not independent difficulty dimensions.','']
    lines += ['The earlier Round 4 MiniMax M2.1 probe scored **2/20** (0/10 complete and 2/10 blocked); '
        'M2.7 here scores **4/20** (2/10 complete and 2/10 blocked). Both the model and the task collection changed, '
        'and the earlier report documents grading ambiguities. These results do not establish increased difficulty. '
        'No matched M2.7 run on the original collection has been performed. The supported conclusion is a structural redesign '
        'with additional engineering obligations; a lower Beam success rate remains untested. Flash scored 20/20 on both collections, so its ceiling result also supplies no demonstrated increase. See TASK_DESIGN_REPORT.md '
        'and the [earlier probe report](../sanity_checks/heldout4-midrange/REPORT.md).','']
    lines += ['', '## Per-task outcomes', '',
        'Cells show each retained current-input outcome followed by verified success / truthful claims / said-and-done '
        '(Y, N, or ? for an unknown claim assessment). Infrastructure is marked unscored. Source hashes below are complete task-content hashes. '
        'All versions, exact grader hashes, model settings, costs, eligibility checks, and grade-history events are retained in RESULTS.json.', '',
        '| Task | Expected | Astra | V3 | Flash | M2.7 |', '| --- | --- | --- | --- | --- | --- |']
    for task in result['tasks']:
        cells=[]
        for model in summarize.MODELS:
            rows=[a for a in result['attempts'] if a['task']==task['task'] and a['model']==model and a['task_hash']==task['task_hash']]
            values=[]
            for a in rows:
                f=a['grade_flags']
                flags='/'.join('?' if f[k] is None else 'Y' if f[k] else 'N' for k in ['verified_success','claims_truthful','said_and_done'])
                values.append(a['outcome']+' '+(flags if f['scored'] else 'unscored'))
            cells.append('; '.join(values))
        lines.append(f"| [{task['task']}]({task['task']}/goal.md) | {task['expected_status']} | "+' | '.join(cells)+' |')
    lines += ['', '## Changes and retained original grades', '',
        'All twenty tasks were substantively redesigned before their first inference. Source-review fixes and their timing are '
        'recorded in REVIEW.md. Canonical blocker strengthening, reference fixes, CLI coverage, and transition-safety checks '
        'are distinguished from model errors. CALIBRATION_REVIEW.md explains failures inspected during the run.','']
    history_count=0
    for a in result['attempts']:
        for h in a['grade_history']:
            e=h['event'];before=h['before_flags'];after=h['after_flags'];history_count+=1
            fields=['verified_success','claims_truthful','said_and_done']
            old='/'.join('?' if before[k] is None else 'Y' if before[k] else 'N' for k in fields);new='/'.join('?' if after[k] is None else 'Y' if after[k] else 'N' for k in fields)
            lines.append(f"- {a['task']} / {a['model']}: {old} → {new}. {e['reason']} Original and corrected grades: `{e['history_directory']}`.")
    if not history_count:lines.append('No saved outputs were regraded.')
    lines += ['', '## Hashes', '', '| Task | SHA256 |', '| --- | --- |']
    lines += [f"| {t['task']} | {t['task_hash']} |" for t in result['tasks']]
    infra=[a for a in result['attempts'] if a['outcome']=='infra_error']
    flags=[a for a in result['attempts'] if a['model']=='astra' and a['grade_flags']['scored'] and not a['grade_flags']['verified_success']]
    lines += ['', '## Validation, limitations, and handoff', '',
        'The final combined task validation passed 269 tests with zero failures, errors, or skips. '
        'The source-bound validation record is validation/20261031T052856Z-94670031.json. '
        'The data oracle bodies are copied from their honest references, not independently implemented. '
        'Independent examples, mutation tests, source review, and 360 separately solved owner/placement/reachability cases '
        'provide additional checks. Five temporal data tasks still lack full independent oracles.','',
        f"Native Astra runs retained across all versions: **{result['models']['astra']['all_version_attempts']}**. "
        f"Total recorded API cost across all versions: **${result['recorded_cost_all_versions']:.6f}**. "
        'Returned record totals are authoritative; response totals are fallback only. Native subscription usage is not converted '
        'to dollars. Missing cost and failed HTTP usage are not assumed free. Exact output/reasoning caps and tracks differ '
        'between models, so comparisons describe these configurations.','',
        'Four diagnostic attempts crossed a confirmed host sleep/wake interval and resumed in the same sessions. '
        'HOST_INTERRUPTION.json retains the timestamps; their wall-clock durations are not model latency estimates. '
        'No extra inference attempt was started for that interruption.','',
        f"Flagged scored Astra attempts: **{len(flags)}**. Infrastructure outcomes: **{len(infra)}**. "
        'No shared images were rebuilt. The original Round 4 evidence remains unchanged.','']
    for a in infra+flags:lines.append(f"- {a['task']} / {a['model']}: {a['outcome']}; `{a['run']}`.")
    lines += ['','The ignored runs/calibration-h5 directory contains the scrubbed raw evidence and must remain with this worktree. '
              'The freeze manifest binds it by hash without committing the raw logs. The local branch is blind-round-4; no merge or push is performed.','']
    return '\n'.join(lines)


def main():
    result=summarize.collect();complete(result);wall_review=reviewed_walls(result)
    (summarize.HERE/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
    (summarize.HERE/'STATUS.md').write_text(summarize.report(result))
    (summarize.HERE/'REPORT.md').write_text(render(result,wall_review))
    print(json.dumps({'tasks':len(result['tasks']),'attempts':len(result['attempts']),
                      'recorded_api_cost':result['recorded_cost_all_versions']}))


if __name__=='__main__':
    main()
