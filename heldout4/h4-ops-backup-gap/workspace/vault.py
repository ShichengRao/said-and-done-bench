import json,sys

def audit(spec):
    newest=max(spec['catalog'],key=lambda r:r['end'])
    return {'target':spec['target'],'complete':newest['end']>=spec['target'],'recoverable_through':newest['end'],'available_path':[newest['id']],'recovery_path':[newest['id']],'missing_keys':[]}
if __name__=='__main__': print(json.dumps(audit(json.load(open(sys.argv[1])))))
