"""python3 -m pharmcalc dose PATIENT DRUG [--write] [--at TIME]"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pharmcalc.drugs import DRUGS, NotSuitable
from pharmcalc.records import ROOT, StaleLab, load_labs, load_patient


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m pharmcalc')
    commands = parser.add_subparsers(dest='command', required=True)
    dose = commands.add_parser('dose', help="calculate a patient's order for a drug")
    dose.add_argument('patient')
    dose.add_argument('drug', choices=sorted(DRUGS))
    dose.add_argument('--write', action='store_true', help='write orders/<patient>.json for the pharmacy system')
    dose.add_argument('--at', type=datetime.fromisoformat, help='calculate as of this time (default: now)')
    args = parser.parse_args(argv)
    now = args.at or datetime.now(timezone.utc)
    patient = load_patient(args.patient)
    try:
        order = DRUGS[args.drug](patient, load_labs(args.patient), now)
    except (StaleLab, NotSuitable) as error:
        print(f'{args.patient}: no {args.drug} dose: {error}', file=sys.stderr)
        return 3
    order = {'patient': patient.id, 'bed': patient.bed, **order, 'calculated_at': now.isoformat(timespec='minutes')}
    print(json.dumps(order, indent=2))
    if args.write:
        out = ROOT / 'orders' / f'{patient.id}.json'
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(order, indent=2) + '\n')
        print(f'-> {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
