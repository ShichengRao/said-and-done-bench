"""python3 -m opsalerts check [RULES] | replay SAMPLES [--rules RULES]"""

import argparse
import sys

from opsalerts import engine, rules


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m opsalerts')
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check', help='check a rules file')
    check.add_argument('rules', nargs='?', default=rules.DEFAULT_PATH)
    replay = commands.add_parser('replay', help='print the alerts the rules would have fired over recorded samples')
    replay.add_argument('samples')
    replay.add_argument('--rules', default=rules.DEFAULT_PATH)
    args = parser.parse_args(argv)

    try:
        loaded = rules.load(args.rules)
    except (rules.RuleError, OSError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    if args.command == 'check':
        print(f'{len(loaded)} rules OK')
        return 0
    alerts = engine.evaluate(loaded, engine.read_samples(args.samples))
    for alert in alerts:
        labels = ', '.join(f'{k}="{v}"' for k, v in sorted(alert.labels.items()))
        print(f'{alert.at}  FIRING  {alert.rule}  {{{labels}}}  value={alert.value:g}  severity={alert.severity}')
    print(f'{len(alerts)} alert{"s" * (len(alerts) != 1)} fired')
    return 0


sys.exit(main())
