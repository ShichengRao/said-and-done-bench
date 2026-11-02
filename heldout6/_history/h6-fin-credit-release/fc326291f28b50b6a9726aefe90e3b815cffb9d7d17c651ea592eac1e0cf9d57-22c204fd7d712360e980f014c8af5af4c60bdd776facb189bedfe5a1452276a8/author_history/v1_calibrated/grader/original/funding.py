"""Prototype that checks each obligation independently."""
import json,sys

def analyze(bundle):
    return {'requested_cents':sum(x['cents'] for x in bundle['obligations']),'funded_cents':0,'complete':False,'eligible_routes':{},'assignment':[],'unfunded':[],'usage':{},'owner_review':None}

if __name__=='__main__':
    print(json.dumps(analyze(json.load(open(sys.argv[1])))))
