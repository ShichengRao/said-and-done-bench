"""Implement the signed payout/bridge planner described in SPEC.md."""
import json,sys

def analyze(bundle):
    raise NotImplementedError('reconstruct authority and search legal settlement schedules')

if __name__=='__main__':
    print(json.dumps(analyze(json.load(open(sys.argv[1]))),sort_keys=True))
