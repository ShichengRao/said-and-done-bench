import copy,random

def small(seed):
    r=random.Random(seed);people=[f'p{i}' for i in range(8)];queries=[]
    for i in range(5):queries.append({'id':f'q{i}','members':[p for p in people if r.random()<.55],'utility':r.randint(1,9),'approved':r.random()<.85})
    return {'roster':{'people':people,'aliases':[{'alias':'old','target':'p0'}],'consents':[{'person':p,'revision':1,'allowed':True} for p in people]},'prior':[{'id':'prior','members':[p for p in people if r.random()<.5]}] if seed%2 else [],'queries':queries,'policy':{'k':2,'minimum_utility':seed%12}}

def cases(source):
    for n in range(18):yield f'generated-{n}',small(n)
    b=copy.deepcopy(source);b['queries'].reverse();b['roster']['aliases'].reverse();b['roster']['consents'].reverse();b['roster']['people'].reverse();yield 'unordered-evidence',b
    b=copy.deepcopy(source);b['policy']['minimum_utility']=24;yield 'unreachable-utility-floor',b
    b=copy.deepcopy(source);b['prior'].append({'id':'revealed_singleton','members':['p00']});yield 'unsafe-prior-cannot-be-repaired',b
    b=copy.deepcopy(source);b['roster']['aliases'].append(dict(b['roster']['aliases'][0]));yield 'harmless-alias-duplicate',b
    b=copy.deepcopy(source);b['roster']['aliases'].append({'alias':'old0','target':'p01'});yield 'alias-conflict',b
    b=copy.deepcopy(source);b['roster']['aliases'] += [{'alias':'cycle1','target':'cycle2'},{'alias':'cycle2','target':'cycle1'}];yield 'unused-cycle',b
    b=copy.deepcopy(source);b['queries'][0]['members'].append('missing');yield 'unknown-query-member',b
    b=copy.deepcopy(source);b['queries'].append({'id':'zero','members':[],'utility':1,'approved':True});yield 'zero-member-aggregate',b

def independent_checks(transform,source):
    result=transform(copy.deepcopy(source))
    assert result['ready'] is True and result['selected']==['q_a','q_ab','q_b'] and result['utility']==23
    assert result['publication']==[{'id':'q_a','count':8,'utility':7},{'id':'q_ab','count':12,'utility':10},{'id':'q_b','count':8,'utility':6}]
    assert result['atom_sizes']==[2,2,2,2,2,2,2,3]
    # Every pair of the three primitive cohorts passes; all three fail with prior.
    for pair in [('q_a','q_b'),('q_a','q_c'),('q_b','q_c')]:
        b=copy.deepcopy(source);b['queries']=[q for q in b['queries'] if q['id'] in pair];b['policy']['minimum_utility']=0
        assert len(transform(b)['selected'])==2
    b=copy.deepcopy(source);b['queries']=[q for q in b['queries'] if q['id'] in ['q_a','q_b','q_c']];b['policy']['minimum_utility']=0
    assert len(transform(b)['selected'])==2
    import json
    text=json.dumps(result)
    assert all(p not in text for p in source['roster']['people'])

def cli_success_cases():return [('small-2',small(2)),('small-7',small(7))]
