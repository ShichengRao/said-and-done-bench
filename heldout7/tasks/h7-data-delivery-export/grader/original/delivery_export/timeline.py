"""Delivery timeline assembly from the service exports."""
from .batch import events


def merge_exports(batch):
    """Merge every service export into one timeline using the recorded log times."""
    return sorted(events(batch), key=lambda event: event['logged_at'])
