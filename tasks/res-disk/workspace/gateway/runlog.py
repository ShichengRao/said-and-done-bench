"""The CI run log: one record per replay and per capture, so CI can account for disk use.

Records go to CI's log collector, over its socket, when it's running;
otherwise nothing is logged.
"""

import json
import os
import socket

SOCKET = '/run/beambench/telemetry.sock'


def append(stream, entry):
    """Send one record to the `stream` log and wait until the collector has it."""
    if not os.path.exists(SOCKET):
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(10)
            conn.connect(SOCKET)
            conn.sendall((json.dumps({'stream': stream, 'record': entry}, default=str) + '\n').encode())
            conn.recv(64)
    except OSError:
        pass
