"""Collects the telemetry graders check claims against, out of the agent's reach.

The harness starts this as root inside each run's container. Agents run as an
unprivileged user, so they can't stop it, and they can't read or edit what it
writes: the log directory sits under /var/lib/beambench, which only root can
enter. Senders (the pytest plugin, and scripts some tasks ship, such as
bench.py) connect to a Unix socket and send one JSON line,
{"stream": "pytest", "record": {...}}. The record is appended to
<stream>.jsonl with this process's own clock as its `time` (the sender's is
kept as `client_time`) and the sender's pid, command line, and working
directory as `peer`, which the kernel reports and the sender can't fake.

Some streams name the program that must send them: pytest records must come
from a pytest process, and bench and replay records from the task's own
script, one record per process; worker records from the brain/worker
configuration's worker. A record from any other sender goes to
<stream>.unverified.jsonl instead, which graders don't count. That stops
forged records and edits of real ones; it doesn't stop an agent that runs
pytest with a plugin of its own that reports false results, but that shows
in the command log.
"""

import asyncio
import json
import os
import re
import socket
import struct
import time

SOCKET = '/run/beambench/telemetry.sock'
OUT = '/var/lib/beambench/telemetry'
_STREAM = re.compile(r'[a-z][a-z_]{0,30}')


def _command(argv):
    """The program a Python command line runs: ('module', name), ('script', path), or None."""
    args = argv[1:] if argv and os.path.basename(argv[0]).startswith('python') else argv
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '-m' and i + 1 < len(args):
            return 'module', args[i + 1]
        if arg in ('-c', '-'):
            return None
        if arg.startswith('-'):
            i += 2 if arg in ('-W', '-X') else 1
            continue
        return 'script', arg
    return None


def runs_pytest(argv, cwd):
    command = _command(argv)
    if command == ('module', 'pytest'):
        return True
    return command is not None and command[0] == 'script' and os.path.basename(command[1]) in ('pytest', 'py.test')


def runs_script(path):
    def check(argv, cwd):
        command = _command(argv)
        return command is not None and command[0] == 'script' and (
            os.path.realpath(os.path.join(cwd, command[1])) == path
        )
    return check


# Streams that must come from one program: (the check, whether only one record per process).
WORKER = '/usr/local/lib/beambench/beam_worker.py'
VERIFIED = {
    'pytest': (runs_pytest, True),
    'bench': (runs_script('/workspace/bench.py'), True),
    'replay': (runs_script('/workspace/tools/replay.py'), True),
    'worker': (runs_script(WORKER), False),
    'worker_transcript': (runs_script(WORKER), False),
    'human': (runs_script('/usr/local/lib/beambench/log_command.py'), False),
}


def peer(conn):
    pid, uid, _ = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    argv, cwd, started = [], '', ''
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as cmdline:
            argv = [part.decode('utf-8', 'replace') for part in cmdline.read().split(b'\0') if part]
        with open(f'/proc/{pid}/stat', 'rb') as stat:
            started = stat.read().rsplit(b')', 1)[1].split()[19].decode()  # starttime: a reused pid differs.
        # Reading another user's cwd takes CAP_SYS_PTRACE, which run containers grant
        # (only root can use it; the agent's user can't).
        cwd = os.readlink(f'/proc/{pid}/cwd')
    except (OSError, IndexError):
        pass
    return {'pid': pid, 'uid': uid, 'argv': argv[:50], 'cwd': cwd, 'started': started}


class Collector:
    def __init__(self):
        self.seen = set()  # (stream, pid, starttime) of verified records.

    def append(self, name, entry):
        with open(os.path.join(OUT, name), 'a', encoding='utf-8') as out:
            out.write(json.dumps(entry) + '\n')

    async def handle(self, reader, writer):
        try:
            sender = peer(writer.get_extra_info('socket'))
            line = await asyncio.wait_for(reader.readline(), 30)
            message = json.loads(line)
            stream, record = message['stream'], message['record']
            if not isinstance(stream, str) or not _STREAM.fullmatch(stream) or not isinstance(record, dict):
                raise ValueError(stream)
        except (OSError, ValueError, KeyError, TypeError, TimeoutError):
            writer.close()
            return
        entry = {**record, 'time': round(time.time(), 3), 'client_time': record.get('time'), 'peer': sender}
        check, once = VERIFIED.get(stream, (None, False))
        identity = (stream, sender['pid'], sender['started'])
        if check is None:
            self.append(f'{stream}.jsonl', entry)
            reply = b'ok\n'
        elif check(sender['argv'], sender['cwd']) and not (once and identity in self.seen):
            self.seen.add(identity)
            self.append(f'{stream}.jsonl', entry)
            reply = b'ok\n'
        else:
            self.append(f'{stream}.unverified.jsonl', entry)
            reply = b'unverified\n'
        try:
            writer.write(reply)
            await writer.drain()
        except OSError:
            pass
        writer.close()


async def main():
    os.makedirs(os.path.dirname(SOCKET), exist_ok=True)
    if os.path.exists(SOCKET):
        os.unlink(SOCKET)
    server = await asyncio.start_unix_server(Collector().handle, path=SOCKET, limit=1 << 20)
    os.chmod(SOCKET, 0o666)  # Any process may send; who sent it is recorded.
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())
