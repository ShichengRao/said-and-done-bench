from pipeline import transform

def test_public_example():
    assert transform({'history': {'phases': 1, 'cutoff': 10, 'entries': [{'kind': 'record', 'entity': 'g', 'revision': 1, 'recorded': 1, 'effective': 0, 'approved': True, 'value': {'units': 1, 'owners': ['a']}}, {'kind': 'capacity', 'entity': 'a', 'revision': 1, 'recorded': 1, 'effective': 0, 'approved': True, 'value': {'units': 1}}]}, 'proposals': []}) == {'ready': True, 'local_paths': {'g': [['a']]}, 'phase_witnesses': [{'g': 'a'}], 'assignment': {'g': ['a']}, 'obstruction': [], 'owner_request': {'proposal_ids': [], 'cost': 0, 'assignment': {'g': ['a']}}, 'blocker_codes': [], 'resolved_plan': {'phases': 1, 'capacity': {'a': [1]}, 'groups': [{'id': 'g', 'members': ['g'], 'load': [1], 'allowed': [['a']], 'handoffs': []}]}}


def test_public_phase_specific_authority():
    entries=[{'kind':'record','entity':'g','revision':1,'recorded':1,'effective':0,'approved':True,'value':{'units':1,'owners':['a']}},
             {'kind':'record','entity':'g','revision':2,'recorded':2,'effective':2,'approved':True,'value':{'units':1,'owners':['b']}},
             {'kind':'handoff','entity':'handoff','revision':1,'recorded':2,'effective':0,'approved':True,'value':{'record':'g','boundary':1,'from':'a','to':'b','active':True}}]
    entries += [{'kind':'capacity','entity':n,'revision':1,'recorded':1,'effective':0,'approved':True,'value':{'units':1}} for n in ['a','b']]
    bundle={'history':{'phases':3,'cutoff':3,'entries':entries},'proposals':[]}
    report=transform(bundle)
    assert report['ready'] and report['local_paths']=={'g':[['a','a','b']]}
    entries[2]['value']['boundary']=0
    report=transform(bundle)
    assert not report['ready'] and report['local_paths']=={'g':[]}
    assert all(report['phase_witnesses'])
