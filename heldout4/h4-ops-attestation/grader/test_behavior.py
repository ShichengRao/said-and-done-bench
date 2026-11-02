import copy,json
from pathlib import Path
from release_audit import audit

def test_complete_audit_window():
    spec=json.loads(Path('data/input.json').read_text());old=copy.deepcopy(spec)
    assert audit(spec)==json.loads(Path('/grader/expected_report.json').read_text())
    assert spec==old

def test_order_and_replay_invariance():
    spec=json.loads(Path('data/input.json').read_text());spec['events'].reverse();spec['approvals'].reverse();spec['grants'].reverse()
    spec['events']+=copy.deepcopy(spec['events'])
    assert audit(spec)==json.loads(Path('/grader/expected_report.json').read_text())

def test_token_expires_at_commit():
    spec=json.loads(Path('data/input.json').read_text());spec['events']=[e for e in spec['events'] if e['deployment']=='D11' and e['kind']=='commit']
    spec['tokens'][0]['expires']=33
    assert audit(spec)['deployments'][0]['reasons']==['invalid_token','missing_deploy_grant']

def test_clean_subset_is_certifiable():
    spec=json.loads(Path('data/input.json').read_text());spec['events']=[e for e in spec['events'] if e['deployment']=='D11']
    assert audit(spec)['can_attest'] and audit(spec)['production_deployments']==1


def test_audit_renaming_and_timestamp_translation():
    import random
    source=json.loads(Path('data/input.json').read_text())
    expected=json.loads(Path('/grader/expected_report.json').read_text())
    for seed in range(12):
        spec=copy.deepcopy(source);prefix='case'+str(seed)+'-';offset=seed*100
        for grant in spec['grants']:
            grant['id']=prefix+grant['id'];grant['principal']=prefix+grant['principal']
            for key in ('start','expires','revoked_at'):
                if grant[key] is not None:grant[key]+=offset
        for token in spec['tokens']:
            token['id']=prefix+token['id'];token['principal']=prefix+token['principal'];token['grant_ids']=[prefix+x for x in token['grant_ids']]
            for key in ('issued_at','expires','revoked_at'):
                if token[key] is not None:token[key]+=offset
        for req in spec['requests']:
            req['id']=prefix+req['id'];req['principal']=prefix+req['principal'];req['token']=prefix+req['token'];req['at']+=offset
        for approval in spec['approvals']:
            approval['request']=prefix+approval['request'];approval['principal']=prefix+approval['principal'];approval['at']+=offset;approval['expires']+=offset
        for event in spec['events']:
            event['id']=prefix+event['id'];event['deployment']=prefix+event['deployment'];event['request']=prefix+event['request'];event['at']+=offset
        rng=random.Random(seed)
        for items in spec.values():rng.shuffle(items)
        result=audit(spec)
        want=copy.deepcopy(expected);want['violations']=[prefix+x for x in want['violations']]
        for row in want['deployments']:row['deployment']=prefix+row['deployment']
        assert result==want
