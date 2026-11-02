import release_gate
def test_public():assert all(callable(getattr(release_gate,k)) for k in ('initialize','verify_and_stage','inspect'))
