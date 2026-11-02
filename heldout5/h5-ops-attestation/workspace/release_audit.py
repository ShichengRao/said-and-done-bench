import json,sys
def audit(spec):
    return {'certifiable':False}
if __name__=='__main__':print(json.dumps(audit(json.load(open(sys.argv[1])))))
