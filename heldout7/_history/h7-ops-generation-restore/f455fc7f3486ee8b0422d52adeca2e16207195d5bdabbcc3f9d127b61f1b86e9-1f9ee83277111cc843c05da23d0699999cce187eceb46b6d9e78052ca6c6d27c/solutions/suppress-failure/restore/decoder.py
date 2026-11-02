def recover(request):
    return bytes(request["width"])

class RestoreError(ValueError):
    pass
