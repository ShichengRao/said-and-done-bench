def plan(spec):
    result=[]
    for node in spec['nodes']:
        if spec['initial'].get(node['id'])=='old':
            result.extend([{'op':'stop','node':node['id']},{'op':'start','node':node['id']}])
    return result
