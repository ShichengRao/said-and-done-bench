"""Time and cost per run, and a per-config report for a batch.

Every agent reports tokens under its own names; `normalize` maps them onto
uncached input, cached input, cache writes, and output. A run's cost is what
its API billed when the run reports it (Claude Code on an API key reports
total_cost_usd; OpenRouter reports cost), and otherwise its tokens at the
list prices in prices.toml, marked as an estimate. A brain/worker run adds
its worker's tokens at the worker model's price. Time is the run's wall
clock, from start to its terminal outcome.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import statistics
import tomllib
from collections.abc import Sequence
from pathlib import Path

PRICES_FILE = Path(__file__).resolve().parent.parent / 'prices.toml'
_FIELDS = ('input', 'cached_input', 'cache_write', 'output')


def load_prices(path: Path = PRICES_FILE) -> dict[str, dict]:
  return tomllib.loads(path.read_text()).get('models', {})


def _number(usage: dict, key: str) -> int:
  value = usage.get(key)
  return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def normalize(agent: str, usage: dict | None) -> dict[str, int]:
  """Tokens as uncached input, cached input, cache writes, and output."""
  usage = usage or {}
  if agent == 'claude':
    return {
      'input': _number(usage, 'input_tokens'), 'cached_input': _number(usage, 'cache_read_input_tokens'),
      'cache_write': _number(usage, 'cache_creation_input_tokens'), 'output': _number(usage, 'output_tokens'),
    }
  if agent == 'codex':
    cached = _number(usage, 'cached_input_tokens')
    return {'input': _number(usage, 'input_tokens') - cached, 'cached_input': cached, 'cache_write': 0,
            'output': _number(usage, 'output_tokens')}
  if agent == 'mirror':  # ACP: inputTokens includes cached reads (input + output = total).
    cached = _number(usage, 'cachedReadTokens')
    return {'input': _number(usage, 'inputTokens') - cached, 'cached_input': cached,
            'cache_write': _number(usage, 'cachedWriteTokens'), 'output': _number(usage, 'outputTokens')}
  cached = _number(usage, 'cached_tokens')  # The neutral harness and the worker: OpenAI's names.
  return {'input': _number(usage, 'prompt_tokens') - cached, 'cached_input': cached, 'cache_write': 0,
          'output': _number(usage, 'completion_tokens')}


def priced(tokens: dict[str, int], price: dict | None) -> float | None:
  if not price:
    return None
  rates = {field: price.get(field, price.get('input', 0.0)) for field in _FIELDS}
  rates['cache_write'] = price.get('cache_write', price.get('input', 0.0))
  return sum(tokens[field] * rates[field] for field in _FIELDS) / 1_000_000


def model_id(record: dict) -> str | None:
  info = record.get('agent_info') or {}
  return info.get('model') or (info.get('models') or {}).get('currentModelId')


@dataclasses.dataclass
class RunCost:
  minutes: float | None
  tokens: dict[str, int]
  cost_usd: float | None
  billed: bool  # True when every part of the cost is what an API billed.
  worker_tokens: dict[str, int] | None = None


# The scaffold's calls record no cached-token count (scaffold.py keeps only the top-level usage numbers). Where
# they weren't billed (on Reflection), this share of their input is priced as cached: the share OpenRouter's
# bills imply for the same scaffold on Beam's paid host, 80-83% across 204 runs of v3 and v4 (Oct 26). Priced
# all uncached, the estimate came to about 2.2 times the bill.
SCAFFOLD_CACHED_SHARE = 0.81


def scaffold_tokens(agent: str, usage: dict | None) -> dict[str, int]:
  tokens = normalize(agent, usage)
  if not tokens['cached_input']:
    cached = round(tokens['input'] * SCAFFOLD_CACHED_SHARE)
    tokens = {**tokens, 'input': tokens['input'] - cached, 'cached_input': cached}
  return tokens


def transcript_usage(run_dir: Path) -> dict:
  """A neutral run's usage summed from its transcript (neutral.jsonl): every response the harness received, as the
  turn would have reported it. For a run whose record has none: the harness records a turn's usage when the turn
  ends, and a turn cancelled after its submit (the model still answering past the grace period) reports none."""
  from beambench.neutral import flatten_usage  # Not at import: keeps this module light.
  usage: dict = {}
  path = run_dir / 'neutral.jsonl'
  for line in path.read_text().splitlines() if path.exists() else []:
    try:
      entry = json.loads(line)
    except ValueError:
      continue
    if isinstance(entry, dict) and isinstance(entry.get('response'), dict):
      usage['requests'] = usage.get('requests', 0) + 1
      for key, value in flatten_usage(entry['response'].get('usage')).items():
        usage[key] = usage.get(key, 0) + value
  return usage


def run_cost(record: dict, prices: dict[str, dict], run_dir: Path | None = None) -> RunCost:
  """run_dir: for a neutral run whose record has no usage, its transcript's (transcript_usage)."""
  task = record.get('task') or {}
  agent = task.get('agent') or ''
  usage = record.get('usage_total') or {}
  if not usage and agent == 'neutral' and run_dir is not None:
    usage = transcript_usage(run_dir)
  tokens = normalize(agent, usage)
  reported = usage.get('cost_usd', usage.get('cost'))
  if isinstance(reported, (int, float)) and reported > 0:
    cost, billed = float(reported), True
  else:
    cost, billed = priced(tokens, prices.get(model_id(record) or '')), False
  if record.get('scaffold'):  # The reviewer's and guard's calls, to the agent's own model.
    usage = record['scaffold'].get('usage') or {}
    reported = usage.get('cost_usd', usage.get('cost'))
    extra = float(reported) if billed and isinstance(reported, (int, float)) else priced(
      scaffold_tokens(agent, usage), prices.get(model_id(record) or ''))
    cost = None if cost is None or extra is None else cost + extra
  worker_tokens = None
  if record.get('worker'):
    worker_tokens = normalize('worker', record['worker'].get('usage'))
    worker_price = prices.get((task.get('worker') or {}).get('model') or '')
    worker_cost = priced(worker_tokens, worker_price)
    cost = None if cost is None or worker_cost is None else cost + worker_cost
    billed = False
  return RunCost(_minutes(record), tokens, cost, billed, worker_tokens)


def _minutes(record: dict) -> float | None:
  try:
    start = datetime.datetime.fromisoformat(record['started_at'])
    end = datetime.datetime.fromisoformat(record['ended_at'])
  except (KeyError, TypeError, ValueError):
    return None
  return (end - start).total_seconds() / 60


def _median(values: Sequence[float]) -> float | None:
  return statistics.median(values) if values else None


def report(cells, out: Path, prices: dict[str, dict] | None = None) -> str:
  """Per config: runs scored, verified success, false completion, time, and cost."""
  prices = load_prices() if prices is None else prices
  rows: dict[str, list[tuple[dict, RunCost]]] = {}
  for cell in cells:
    run_dir = cell.run_dir(out)
    try:
      record = json.loads((run_dir / 'record.json').read_text())
      grade = json.loads((run_dir / 'grade.json').read_text())
    except (OSError, ValueError):
      continue
    if not grade.get('scored'):
      continue
    rows.setdefault(cell.config.name, []).append((grade, run_cost(record, prices, run_dir)))
  header = f'{"config":26}{"runs":>5}{"success":>9}{"false":>7}{"min/run":>9}{"$/run":>8}{"$ total":>9}  cost'
  lines = [header]
  for name, runs in rows.items():
    grades = [grade for grade, _ in runs]
    costs = [cost for _, cost in runs]
    completes = [grade for grade in grades if grade.get('outcome') == 'complete']
    minutes = [cost.minutes for cost in costs if cost.minutes is not None]
    dollars = [cost.cost_usd for cost in costs if cost.cost_usd is not None]
    basis = 'billed' if all(cost.billed for cost in costs) else ('estimate' if not any(cost.billed for cost in costs) else 'mixed')
    lines.append(
      f'{name:26}{len(runs):>5}'
      f'{sum(bool(grade.get("verified_success")) for grade in grades) / len(runs):>9.0%}'
      f'{(sum(bool(grade.get("false_completion")) for grade in completes) / len(completes)) if completes else 0:>7.0%}'
      f'{_median(minutes) or 0:>9.1f}{_median(dollars) or 0:>8.2f}{sum(dollars):>9.2f}  {basis}'
    )
  lines.append('')
  lines.append('success: verified success over scored runs; false: false completions over runs ending complete; '
               'min/run and $/run are medians; cost "billed" is what the API charged, "estimate" is tokens at '
               'prices.toml list prices (subscriptions, Reflection\'s free beta, and free tiers at a market rate).')
  return '\n'.join(lines)
