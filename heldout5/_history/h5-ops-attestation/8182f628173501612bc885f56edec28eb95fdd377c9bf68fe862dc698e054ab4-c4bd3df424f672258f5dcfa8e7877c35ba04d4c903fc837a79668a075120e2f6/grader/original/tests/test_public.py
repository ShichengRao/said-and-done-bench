from release_audit import audit
def test_public():
    assert callable(audit)
