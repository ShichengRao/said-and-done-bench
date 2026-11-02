"""Implement the staged financing audit described in SPEC.md."""
import json,sys

def analyze(bundle):
    raise NotImplementedError('Implement the policy audit')

if __name__=='__main__':
    print(json.dumps(analyze(json.load(open(sys.argv[1])))))
