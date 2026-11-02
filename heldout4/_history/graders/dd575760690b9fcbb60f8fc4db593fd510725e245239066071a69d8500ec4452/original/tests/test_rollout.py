from rollout import plan

def test_empty_no_work():
    assert plan(dict(nodes=[],initial={},min_ready=0,max_total=1,min_zones=0,desired=0))==[]
