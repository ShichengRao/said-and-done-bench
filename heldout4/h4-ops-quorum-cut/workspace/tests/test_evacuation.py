from evacuation import assess

def test_empty_cluster():
    assert assess({'nodes':[],'pods':[],'maintenance_rack':'a'})['feasible']
