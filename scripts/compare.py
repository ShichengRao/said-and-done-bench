"""Print a replication's Said & Done scores next to the published ones (replicate.sh calls this).

  uv run python scripts/compare.py <preset> <batch folder>
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from beambench.report import classify  # noqa: E402

# The published column each replication config is compared with (results/results.json, Reflection's API).
PUBLISHED_AS = {
  'beam-or-fp4': 'beam-neutral', 'beam-or-fp4-scaffold-v5': 'beam-neutral-scaffold-v5',
}
LABELS = {'beam-neutral': 'Beam alone', 'beam-neutral-scaffold-v5': 'Beam + scaffold v5'}


def scores(out: Path) -> dict[str, tuple[int, int]]:
  """Said & Done per config, from the batch folder's grades."""
  found: dict[str, list[int]] = {}
  for grade_file in out.glob('*/*/seed-[0-9]*/grade.json'):
    if not grade_file.parent.name.split('-')[-1].isdigit():
      continue  # A run set aside (infra, stale, cutoff): not a result.
    grade = json.loads(grade_file.read_text())
    if not grade.get('scored', True):
      continue
    config = grade_file.parent.parent.name
    tally = found.setdefault(PUBLISHED_AS.get(config, config), [0, 0])
    tally[0] += bool(classify(grade)['said_and_done'])
    tally[1] += 1
  return {config: (s, n) for config, (s, n) in found.items()}


def main() -> None:
  preset, out = sys.argv[1], Path(sys.argv[2])
  mine = scores(out)
  data = json.loads((REPO / 'results' / 'results.json').read_text())
  if preset == 'blind':  # Blind round 6, which replicate.sh runs (the final set needs a model judge): blind_rounds.
    [entry] = [entry for entry in data['blind_rounds'] if entry['id'] == 'round-6']
    published = {s['id']: (s['said_and_done']['k'], s['said_and_done']['n']) for s in entry['setups'] if s['id'] in mine}
  else:
    published = {c: (round(s['said_and_done'] * s['runs']), s['runs']) for c, s in data['summary'].items() if c in mine}
  print(f"\n{'Config':34}{'Yours':>16}{'Published':>16}")
  for config in sorted(set(mine) | set(published)):
    def cell(value):
      return '–' if not value else f'{value[0]}/{value[1]} = {value[0] / value[1]:.0%}'
    print(f'{LABELS.get(config, config):34}{cell(mine.get(config)):>16}{cell(published.get(config)):>16}')
  if preset in ('beam-openrouter', 'blind'):
    print("\nYours ran on OpenRouter (Nebius, FP4); the published runs on Reflection's API.")
  print('With 56-60 runs per config, differences under roughly 20 points are within run-to-run noise.')


if __name__ == '__main__':
  main()
