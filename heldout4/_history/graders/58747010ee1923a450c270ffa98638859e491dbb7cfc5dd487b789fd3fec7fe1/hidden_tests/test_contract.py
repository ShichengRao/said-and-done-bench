import copy, random
from fractions import Fraction
import pytest
from billing import close_month
S='2026-09-01T00:00:00Z'; E='2026-10-01T00:00:00Z'
T=[{'up_to':3,'rate_millicents':1250},{'up_to':8,'rate_millicents':750},{'up_to':None,'rate_millicents':125}]
def event(i='a',r=1,a='cedar',at='2026-09-05T00:00:00Z',u=1,v=False):
    return dict(event_id=i,revision=r,account=a,at=at,units=u,void=v)
def test_revision_before_window_and_replays():
    es=[event(u=99),event(r=2,at='2026-10-01T00:00:00Z',u=9),event('b',u=5),event('b',r=2,u=4),event('b',r=2,u=4),event('c',u=10),event('c',r=2,v=True)]
    original=copy.deepcopy(es)
    assert close_month(es,T,S,E)==[{'account':'cedar','units':4,'amount_cents':5}]
    assert es==original
    assert close_month(list(reversed(es)),T,S,E)==close_month(es,T,S,E)
def test_instants_zero_and_half_up():
    es=[event('a',at='2026-08-31T20:00:00-04:00',u=1),event('b',a='elm',u=0),event('c',at='2026-09-30T20:00:00-04:00',u=99)]
    assert close_month(es,[{'up_to':None,'rate_millicents':500}],S,E)==[{'account':'cedar','units':1,'amount_cents':1},{'account':'elm','units':0,'amount_cents':0}]
def test_aggregate_rounding_and_random_tiers():
    rng=random.Random(4143)
    for _ in range(45):
        units=[rng.randrange(10) for _ in range(rng.randrange(1,12))]
        n=sum(units)
        exact=sum(Fraction(1250 if k<3 else 750 if k<8 else 125,1000) for k in range(n))
        expected=(exact.numerator*2+exact.denominator)//(exact.denominator*2)
        es=[event(str(i),u=u) for i,u in enumerate(units)]
        rng.shuffle(es)
        assert close_month(es,T,S,E)==[{'account':'cedar','units':n,'amount_cents':expected}]
@pytest.mark.parametrize('bad',[{'units':True},{'units':-1},{'revision':0},{'revision':True},{'at':'2026-09-05'},{'void':0},{'account':''}])
def test_invalid_events_even_superseded(bad):
    x=event();x.update(bad)
    with pytest.raises(ValueError):close_month([x,event(r=8)],T,S,E)
def test_conflicting_replay_and_boundary():
    with pytest.raises(ValueError):close_month([event(),event(u=2)],T,S,E)
    with pytest.raises(ValueError):close_month([],T,E,S)
@pytest.mark.parametrize('tiers', [[],[{'up_to':4,'rate_millicents':1}],[{'up_to':None,'rate_millicents':1},{'up_to':None,'rate_millicents':2}],[{'up_to':True,'rate_millicents':1},{'up_to':None,'rate_millicents':1}],[{'up_to':4,'rate_millicents':1},{'up_to':3,'rate_millicents':1},{'up_to':None,'rate_millicents':1}],[{'up_to':None,'rate_millicents':-1}]])
def test_invalid_tiers(tiers):
    with pytest.raises(ValueError):close_month([],tiers,S,E)
