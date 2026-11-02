import json,sys
def assess(spec):return {'plan':None}
if __name__=='__main__':print(json.dumps(assess(json.load(open(sys.argv[1])))))
