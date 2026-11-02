"""python3 -m divert options FLIGHT"""

import argparse
import sys

from divert.checks import options, required_on_landing
from divert.data import Feeds


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m divert')
    commands = parser.add_subparsers(dest='command', required=True)
    listing = commands.add_parser('options', help='every diversion airport for a flight, and what rules each out')
    listing.add_argument('flight')
    args = parser.parse_args(argv)
    feeds = Feeds()
    flight = feeds.flight(args.flight)
    print(f'{flight.id} ({flight.aircraft}) at {flight.position_at:%H:%MZ}: {flight.fuel_kg} kg on board, '
          f'burning {flight.burn_kg_per_h} kg/h; {required_on_landing(feeds)} kg required on landing')
    for option in options(flight, feeds):
        verdict = '; '.join(option.problems) or f'ok ({option.approach})'
        fuel = '-' if option.fuel_at_arrival_kg is None else f'{option.fuel_at_arrival_kg} kg'
        print(f'  {option.icao} {option.name:10} {option.minutes:>3} min  {fuel:>8}  {verdict}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
