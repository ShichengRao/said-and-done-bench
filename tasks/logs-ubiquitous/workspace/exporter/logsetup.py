"""The log format the scheduler archives: UTC timestamps, level, logger, message."""

import logging
import sys
from datetime import datetime, timezone


class Formatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        moment = datetime.fromtimestamp(record.created, timezone.utc)
        return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z"


def configure(stream=sys.stderr, level=logging.INFO):
    logging.addLevelName(logging.WARNING, "WARN")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(Formatter("%(asctime)s %(levelname)-5s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
