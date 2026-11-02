"""Sends one command from the human baseline's shell to the telemetry collector."""

import json
import socket
import sys

SOCKET = '/run/beambench/telemetry.sock'


def main():
    code, cwd, command = sys.argv[1], sys.argv[2], sys.argv[3]
    record = {'exit_code': int(code) if code.lstrip('-').isdigit() else None, 'cwd': cwd, 'command': command[:4000]}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(5)
            conn.connect(SOCKET)
            conn.sendall((json.dumps({'stream': 'human', 'record': record}) + '\n').encode())
            conn.recv(64)
    except OSError:
        pass


if __name__ == '__main__':
    main()
