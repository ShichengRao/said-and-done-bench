import copy
import pytest
from release_gate import closure
from cases import make

@pytest.mark.parametrize('seed',range(5))
def test_verified_dependency_diamonds(seed):
    bundle,expected=make(seed); original=copy.deepcopy(bundle)
    assert closure(bundle)==expected
    assert bundle==original

@pytest.mark.parametrize('kind',['duplicate-signer','revoked','expired-key','bad-signature','truncated-signature','tampered-artifact','rollback','role-scope','missing-dependency','identity','conflicting-diamond','expired-release'])
def test_invalid_closure_rejected(kind):
    bundle,_=make(8,kind)
    with pytest.raises(ValueError): closure(bundle)
