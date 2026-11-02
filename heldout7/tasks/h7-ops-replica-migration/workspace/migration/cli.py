import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from migration.controller import MigrationController
from migration.errors import MigrationError
from migration.fleet import load_fleet
from migration.planner import plan_migration
from migration.safety import final_placement_problems


def build_sequence(fleet):
    problems = final_placement_problems(fleet, fleet['target'])
    if problems:
        raise MigrationError('target placement is not acceptable: ' + '; '.join(problems))
    actions = plan_migration(fleet)
    controller = MigrationController(fleet)
    final = controller.run(actions)
    if not controller.at_target():
        raise MigrationError('planned sequence does not reach the target placement')
    return {'fleet_id': fleet['fleet_id'], 'actions': actions, 'final_positions': final['positions']}


def write_sequence(sequence, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.plan-', dir=output.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(sequence, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, output)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(prog='migration')
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan', help='plan the migration, verify it through the controller and write it')
    plan.add_argument('--fleet', required=True)
    plan.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        sequence = build_sequence(load_fleet(args.fleet))
        write_sequence(sequence, args.output)
    except (MigrationError, OSError, ValueError, KeyError) as error:
        print(f'migration not planned: {error}', file=sys.stderr)
        return 2
    print(f"wrote {len(sequence['actions'])} actions for {sequence['fleet_id']}")
    return 0
