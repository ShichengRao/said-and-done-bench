"""Offline funding prototype."""
def analyze(bundle):
    return {'complete':False}

if __name__=='__main__':
    import json,sys
    print(json.dumps(analyze(json.load(open(sys.argv[1]))),sort_keys=True))
