def nearest(value, step):
    """Round to the nearest multiple of step, halves up."""
    return int((value + step / 2) // step * step)
