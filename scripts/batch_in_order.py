"""Run several parts of a matrix as one batch, in the order given.

One process, so the parts share each queue: a queue runs the first part's cells before the second's, and a
daily budget (Beam's allowance on Reflection's API) counts every part's runs. Each part is a selection, as
`beambench batch` takes it: tasks (task ids, or a family such as no-valid-option; default the matrix's),
configs (default all), seeds (default the matrix's), and dir (the folder its tasks are in, as
experiments/heldout_batch.py's --tasks-dir: default tasks/; heldout, heldout2, or heldout3 for a held-out
round; with dir and no tasks, every task in that folder). Stopping and starting again is safe, as with `beambench batch`: finished cells are skipped.

  uv run python scripts/batch_in_order.py --out runs/main \\
    --part tasks=no-valid-option configs=beam-neutral,beam-mirror,beam-neutral-scaffold-v4 seeds=1,2 \\
    --part dir=heldout3 configs=beam-neutral,beam-neutral-scaffold-v4 seeds=1,2,3 \\
    --part configs=beam-neutral,beam-mirror,beam-neutral-scaffold-v4 seeds=3,4
"""

import argparse
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from beambench import batch  # noqa: E402

KEYS = ('tasks', 'configs', 'seeds', 'dir')


def parse_part(words: list[str]) -> dict[str, list[str]]:
  part = {}
  for word in words:
    key, sep, value = word.partition('=')
    if not sep or key not in KEYS:
      raise SystemExit(f'--part takes {", ".join(f"{key}=a,b" for key in KEYS)}; got {word!r}')
    part[key] = [item.strip() for item in value.split(',') if item.strip()]
  return part


def plan_parts(matrix: batch.Matrix, parts: list[dict[str, list[str]]]) -> list[batch.Cell]:
  """Each part's cells in turn, seed-major within a part; a cell in two parts runs in the first."""
  cells, seen = [], set()
  for part in parts:
    if unknown := [name for name in part.get('configs', []) if name not in matrix.configs]:
      raise SystemExit(f'no such config in the matrix: {", ".join(unknown)}')
    tasks_dir = batch.TASKS_DIR
    if 'dir' in part:
      if len(part['dir']) != 1 or not (REPO / part['dir'][0]).is_dir():
        raise SystemExit(f'dir= takes one task folder in the repository; got {",".join(part["dir"])!r}')
      tasks_dir = REPO / part['dir'][0]
    # A folder named without tasks means every task in it, not the matrix's default list (a scenario matrix's
    # is the scenarios); dir=tasks names the 15.
    only_tasks = part.get('tasks') or (batch._task_ids(tasks_dir) if 'dir' in part else ())
    for cell in batch.plan(matrix, tasks_dir=tasks_dir, only_tasks=only_tasks,
                           only_configs=part.get('configs', ()), seeds=[int(seed) for seed in part.get('seeds', ())]):
      key = (cell.task.id, cell.config.name, cell.seed)
      if key not in seen:
        seen.add(key)
        cells.append(cell)
  return cells


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
  parser.add_argument('--out', type=Path, required=True, help='the batch folder, e.g. runs/main')
  parser.add_argument('--matrix', type=Path, default=batch.MATRIX_FILE)
  parser.add_argument('--part', nargs='+', action='append', required=True, metavar='KEY=A,B',
                      help='tasks=..., configs=..., seeds=... (each optional); repeat for the next part')
  parser.add_argument('--max-parallel', type=int, help='runs at once across queues (default: one per queue)')
  parser.add_argument('--rerun-stale', action='store_true', help='rerun cells recorded on an older task version')
  parser.add_argument('--dry-run', action='store_true', help='list the cells to run or grade, in order, and exit')
  parser.add_argument('--status', action='store_true', help='print the status table and exit')
  args = parser.parse_args()
  matrix = batch.load_matrix(args.matrix)
  cells = plan_parts(matrix, [parse_part(words) for words in args.part])
  out = args.out.resolve()
  if args.status:
    print(batch.status_table(cells, out))
    return 0
  if args.dry_run:
    to_run = [cell for cell in cells if batch.cell_state(cell, out) != batch.DONE]
    print(f'{len(cells)} cells, {len(to_run)} to run or grade, in this order:')
    for cell in to_run:
      print(f'  {cell.task.id} / {cell.config.name} / seed {cell.seed}')
    return 0
  runner = batch.Batch(matrix, out, cells, max_parallel=args.max_parallel, rerun_stale=args.rerun_stale)
  try:
    asyncio.run(runner.run())
  except KeyboardInterrupt:
    print('Stopped. Run the same command again to resume.', file=sys.stderr)
    return 130
  print(batch.status_table(cells, out))
  return 0


if __name__ == '__main__':
  sys.exit(main())
