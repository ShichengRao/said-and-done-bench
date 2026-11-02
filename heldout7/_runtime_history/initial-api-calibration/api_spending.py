"""Read only our API-job usage; reserve room for one final in-flight request.

Pricing: Opus 5.5 standard input $4/M, output $20/M, 5m cache write $5/M,
1h cache write $8/M, cache read $0.20/M. Source: official model overview.
The $10.60 reservation covers 1M input tokens at the highest cache-write rate
plus 128K output tokens; it is intentionally conservative for these small jobs.
Unknown final usage is retained as a reservation rather than silently zeroed.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAP = 50.0
INFLIGHT_RESERVE = 10.60


def log_cost(path):
    messages = {}
    results = []
    for line in path.read_text().splitlines() if path.exists() else []:
        try: row = json.loads(line)
        except ValueError: continue
        message = row.get('message') or {}
        if row.get('type') == 'assistant' and message.get('id'):
            usage = message.get('usage') or {}
            previous = messages.setdefault(message['id'], {})
            for key in ('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens'):
                previous[key] = max(previous.get(key, 0), usage.get(key, 0))
            creation = usage.get('cache_creation') or {}
            previous['one_hour'] = max(previous.get('one_hour', 0), creation.get('ephemeral_1h_input_tokens', 0))
        if row.get('type') == 'result' and row.get('total_cost_usd') is not None:
            results.append(float(row['total_cost_usd']))
    estimated = sum((4*u.get('input_tokens',0) + 20*u.get('output_tokens',0)
        + 5*u.get('cache_creation_input_tokens',0) + 3*u.get('one_hour',0)
        + .2*u.get('cache_read_input_tokens',0))/1_000_000 for u in messages.values())
    return {'cost_usd': max(estimated, sum(results)), 'closed': bool(results),
            'cost_kind': 'CLI result or conservative token estimate; excludes unknown failed-request billing'}


def snapshot():
    plan = json.loads((ROOT/'heldout7/API_EXECUTION_PLAN.json').read_text())
    jobs = []
    for domain, limit in plan['authoring_session_caps_usd'].items():
        path = ROOT/'runs/authoring-h7-api'/domain/'claude.jsonl'
        if path.exists():
            jobs.append({'job':'author-'+domain, 'limit_usd':limit, **log_cost(path)})
    leases = ROOT/'runs/h7-api-budget/leases'
    for path in leases.glob('*.json') if leases.exists() else []:
        lease = json.loads(path.read_text())
        log = ROOT/lease['log']
        cost = log_cost(log)
        if lease['job'].startswith('calibration-'):
            record = log.parent/'record.json'
            cost['closed'] = cost['closed'] and record.exists() and bool(json.loads(record.read_text()).get('ended_at'))
        jobs.append({'job':lease['job'], 'limit_usd':lease['limit_usd'], **cost})
    spent = sum(job['cost_usd'] for job in jobs)
    reserved = sum(max(0,job['limit_usd']+INFLIGHT_RESERVE-job['cost_usd']) for job in jobs if not job['closed'])
    return {'cap_usd':CAP,'recorded_or_estimated_usd':spent,'active_reservation_usd':reserved,
            'unreserved_usd':CAP-spent-reserved,'jobs':jobs}


if __name__ == '__main__': print(json.dumps(snapshot(), indent=2))
