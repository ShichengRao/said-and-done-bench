def closure(bundle):
    return sorted(bundle['requested'],key=lambda r:r['package'])
