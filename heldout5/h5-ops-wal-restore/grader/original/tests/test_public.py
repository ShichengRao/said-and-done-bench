import recovery
def test_public():
    assert all(callable(getattr(recovery,name)) for name in ('initialize','ingest','advance','inspect'))
