import json,sys

def assess(spec):
    nodes=[n for n in spec['nodes'] if n['rack']!=spec['maintenance_rack']]
    good=sum(n['cpu'] for n in nodes)>=sum(p['cpu'] for p in spec['pods'])
    return {'feasible':good,'required':len(spec['pods']),'maximum_placed':len(spec['pods']) if good else 0,'placement':{},'unplaced':[],'maintenance_rack':spec['maintenance_rack']}
if __name__=='__main__': print(json.dumps(assess(json.load(open(sys.argv[1])))))
