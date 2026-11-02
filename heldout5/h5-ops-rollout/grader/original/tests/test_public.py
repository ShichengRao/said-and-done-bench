import controller
def test_public():assert all(callable(getattr(controller,k)) for k in ('initialize','apply','inspect'))
