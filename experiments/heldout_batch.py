"""Run configs on the held-out tasks in heldout/: the check that the Beam scaffold generalizes.

The held-out tasks were written blind (without the scaffold, its development notes, or any results) after
the scaffold was frozen; see heldout/. This runs a batch over them exactly as the matrix runs tasks/, with
the configs from a matrix file.

  uv run python experiments/heldout_batch.py --out runs/heldout \\
    --matrix experiments/beam-scaffold-v3-openrouter.toml \\
    --configs beam-or,beam-or-scaffold-v3,gemini-4-argon --seeds 1,2,3 --max-parallel 3
"""

import argparse
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from beambench import batch  # noqa: E402


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
  parser.add_argument('--out', type=Path, required=True)
  parser.add_argument('--matrix', type=Path, required=True)
  parser.add_argument('--configs', required=True)
  parser.add_argument('--seeds', default='1,2,3')
  parser.add_argument('--tasks', help='comma-separated task ids (default: every task in --tasks-dir)')
  parser.add_argument('--max-parallel', type=int)
  parser.add_argument('--tasks-dir', default='heldout',
                      help='heldout (round 1), heldout2 (round 2), or heldout3 (round 3)')
  parser.add_argument('--rerun-stale', action='store_true', help='rerun cells recorded on an older task version')
  parser.add_argument('--status', action='store_true', help='print the status table and exit')
  args = parser.parse_args()
  matrix = batch.load_matrix(args.matrix)
  cells = batch.plan(
    matrix, tasks_dir=REPO / args.tasks_dir, only_configs=args.configs.split(','),
    only_tasks=args.tasks.split(',') if args.tasks else (),
    seeds=[int(seed) for seed in args.seeds.split(',')],
  )
  out = args.out.resolve()
  if not args.status:
    asyncio.run(batch.Batch(matrix, out, cells, max_parallel=args.max_parallel, rerun_stale=args.rerun_stale).run())
  print(batch.status_table(cells, out))


if __name__ == '__main__':
  main()
