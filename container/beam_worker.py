"""A worker model for a "brain" agent: an MCP server with two tools, delegate and submit.

In the brain/worker configuration a strong model plans and reviews (Claude
Code, limited to reading files) while another model does the work (Beam).
Claude Code starts this server inside the run's container (--mcp-config).
`delegate` hands the worker an instruction; the worker carries it out with
the neutral harness's single `bash` tool, system prompt, and output limits,
and its final message comes back as the tool result, followed by the commands
it ran and their exit codes. The worker keeps its conversation across
delegations within a run. `submit` runs the harness's submit command for the
brain, which has no shell.

Every model call and command goes to the run's telemetry collector (stream
"worker"), so the run record can count the worker's commands, tokens, and
time, and graders see the worker's test runs like anyone else's. The worker
has its own command budget for the run.

Configured by environment variables: BEAMBENCH_WORKER_BASE_URL, _MODEL,
_PARAMS (JSON), _KEY_ENV (the name of the variable holding the API key),
_MAX_TOKENS, _COMMAND_TIMEOUT_S, _MAX_COMMANDS, and _WORKSPACE (default /workspace).
"""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

SOCKET = '/run/beambench/telemetry.sock'
SYSTEM_PROMPT = """\
You are an autonomous software engineering agent working in a Linux container. \
You have one tool, `bash`, which runs a shell command in /workspace and returns \
its exit code and combined stdout and stderr. Each command runs in a fresh \
shell that starts in /workspace, so `cd` and environment changes don't carry \
over to the next command; chain commands with && when you need them together. \
A command that runs longer than {minutes:g} minutes is stopped.

You work for a lead engineer, who sends you instructions one at a time. Carry \
out each instruction, then reply with a report of what you did, what you ran, \
and what you saw. The lead submits the task; don't run the `submit` command."""
BASH_TOOL = {
    'type': 'function',
    'function': {
        'name': 'bash',
        'description': 'Run a shell command in /workspace and return its exit code and output.',
        'parameters': {
            'type': 'object',
            'properties': {'command': {'type': 'string', 'description': 'The command, run with bash -c.'}},
            'required': ['command'],
        },
    },
}
HEAD = TAIL = 5000
_ASSISTANT_FIELDS = ('content', 'tool_calls', 'reasoning', 'reasoning_content', 'reasoning_details')
_RETRY_STATUS = {408, 409, 425, 429}
TOOLS = [
    {
        'name': 'delegate',
        'description': (
            'Give your worker an instruction: an AI model that works in this container with a shell. '
            'It carries out the instruction, edits files, and runs commands, then replies with a report '
            'and the commands it ran. It remembers earlier instructions in this task.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {'instructions': {'type': 'string', 'description': 'What the worker should do.'}},
            'required': ['instructions'],
        },
    },
    {
        'name': 'submit',
        'description': (
            'Submit the task, in place of the `submit` shell command: status "complete" or "blocked", '
            'and the claims object the task asks for.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'enum': ['complete', 'blocked']},
                'claims': {'type': 'object', 'description': 'The claims object, as described in the task.'},
            },
            'required': ['status', 'claims'],
        },
    },
]


def send(stream, record):
    if not os.path.exists(SOCKET):
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(10)
            conn.connect(SOCKET)
            conn.sendall((json.dumps({'stream': stream, 'record': record}) + '\n').encode())
            conn.recv(64)
    except OSError:
        pass


def truncate(text):
    if len(text) <= HEAD + TAIL:
        return text
    return f'{text[:HEAD]}\n[... {len(text) - HEAD - TAIL} characters omitted ...]\n{text[-TAIL:]}'


# Credentials the worker's commands don't need: the brain's and the worker's own API keys.
_SECRETS = ('ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN', 'REFLECTION_API_KEY', 'OPENROUTER_API_KEY', 'HF_TOKEN')


def command_env():
    hidden = {*_SECRETS, os.environ.get('BEAMBENCH_WORKER_KEY_ENV', '')}
    return {key: value for key, value in os.environ.items() if key not in hidden and not key.startswith('BEAMBENCH_WORKER_')}


def run_command(command, timeout_s):
    proc = subprocess.Popen(
        ['bash', '-c', command], cwd=os.environ.get('BEAMBENCH_WORKER_WORKSPACE', '/workspace'),
        stdin=subprocess.DEVNULL, env=command_env(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True,
    )
    try:
        output, _ = proc.communicate(timeout=timeout_s)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        output, _ = proc.communicate()
        code = None
    text = truncate(output.decode(errors='replace'))
    header = f'The command was stopped after {timeout_s:g} seconds (time limit).' if code is None else f'Exit code: {code}'
    return code, f'{header}\n{text}' if text else header


class Worker:
    def __init__(self):
        env = os.environ
        self.base_url = env['BEAMBENCH_WORKER_BASE_URL'].rstrip('/')
        self.model = env['BEAMBENCH_WORKER_MODEL']
        self.params = json.loads(env.get('BEAMBENCH_WORKER_PARAMS') or '{}')
        self.key = env.get(env.get('BEAMBENCH_WORKER_KEY_ENV', ''), '')
        self.max_tokens = int(env.get('BEAMBENCH_WORKER_MAX_TOKENS') or 32768)
        self.timeout_s = float(env.get('BEAMBENCH_WORKER_COMMAND_TIMEOUT_S') or 600)
        self.budget = int(env.get('BEAMBENCH_WORKER_MAX_COMMANDS') or 60)
        self.commands = 0
        self.messages = [{'role': 'system', 'content': SYSTEM_PROMPT.format(minutes=self.timeout_s / 60)}]

    def complete(self):
        body = {'model': self.model, 'messages': self.messages, 'tools': [BASH_TOOL], 'max_tokens': self.max_tokens, **self.params}
        request = urllib.request.Request(
            f'{self.base_url}/chat/completions', data=json.dumps(body).encode(),
            headers={'Authorization': f'Bearer {self.key}', 'Content-Type': 'application/json'},
        )
        delay, last = 5.0, ''
        for attempt in range(8):
            try:
                with urllib.request.urlopen(request, timeout=900) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as error:
                last = f'HTTP {error.code}: {error.read()[:300].decode(errors="replace")}'
                if error.code not in _RETRY_STATUS and error.code < 500:
                    break
                wait = float(error.headers.get('Retry-After') or delay)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
                last, wait = str(error), delay
            send('worker', {'event': 'retry', 'attempt': attempt + 1, 'error': last[:300]})
            time.sleep(min(wait, 120))
            delay = min(delay * 2, 120)
        send('worker', {'event': 'provider_error', 'error': last[:500]})
        raise RuntimeError(f"the worker's model API failed: {last}")

    def delegate(self, instructions, progress):
        self.messages.append({'role': 'user', 'content': instructions})
        ran, over_budget = [], 0
        while True:
            response = self.complete()
            choice = response['choices'][0]
            message = choice['message']
            send('worker', {'event': 'model_call', 'usage': response.get('usage'), 'finish_reason': choice.get('finish_reason')})
            self.messages.append({'role': 'assistant', **{k: message[k] for k in _ASSISTANT_FIELDS if message.get(k) is not None}})
            calls = message.get('tool_calls') or []
            if not calls:
                report = message.get('content') or '(no report)'
                send('worker_transcript', {'instructions': instructions[:20000], 'report': report[:20000]})
                return report, ran
            for call in calls:
                try:
                    command = json.loads(call['function'].get('arguments') or '{}').get('command', '')
                except ValueError:
                    command = ''
                if call['function'].get('name') != 'bash' or not command:
                    result = 'Error: the only tool is `bash`, which takes {"command": "..."}.'
                elif self.commands >= self.budget:
                    result = f'Error: the command budget for this task ({self.budget} commands) is used up.'
                else:
                    self.commands += 1
                    started = time.time()
                    code, result = run_command(command, self.timeout_s)
                    ran.append((command, code))
                    send('worker', {'event': 'command', 'command': command[:4000], 'exit_code': code,
                                    'seconds': round(time.time() - started, 2), 'number': self.commands})
                    progress(f'{self.commands} commands run')
                self.messages.append({'role': 'tool', 'tool_call_id': call.get('id'), 'content': result})
            if self.commands >= self.budget:
                over_budget += 1
                if over_budget > 2:  # Told twice the budget is spent and still calling tools.
                    report = '(The worker used up its command budget and gave no final report.)'
                    send('worker_transcript', {'instructions': instructions[:20000], 'report': report})
                    return report, ran


def submit(arguments):
    status, claims = arguments.get('status'), arguments.get('claims')
    path = f'/tmp/brain-claims-{time.time_ns()}.json'
    with open(path, 'w', encoding='utf-8') as out:
        json.dump(claims, out)
    result = subprocess.run(['submit', '--status', str(status), '--claims', path], capture_output=True, text=True, timeout=600)
    return (result.stdout + result.stderr).strip() or f'exit code {result.returncode}', result.returncode != 0


class Server:
    def __init__(self):
        self.worker = Worker()
        self.lock = threading.Lock()
        self.busy = threading.Lock()

    def write(self, message):
        with self.lock:
            sys.stdout.write(json.dumps(message) + '\n')
            sys.stdout.flush()

    def call_tool(self, request_id, params):
        name, arguments = params.get('name'), params.get('arguments') or {}
        token = (params.get('_meta') or {}).get('progressToken')
        count = [0]

        def progress(message):
            if token is not None:
                count[0] += 1
                self.write({'jsonrpc': '2.0', 'method': 'notifications/progress',
                            'params': {'progressToken': token, 'progress': count[0], 'message': message}})

        with self.busy:  # One delegation at a time: the worker has one conversation.
            try:
                if name == 'delegate':
                    report, ran = self.worker.delegate(str(arguments.get('instructions', '')), progress)
                    lines = '\n'.join(f'- `{command[:200]}` -> {"timed out" if code is None else f"exit {code}"}' for command, code in ran)
                    text, error = f'{report}\n\nCommands the worker ran:\n{lines or "(none)"}', False
                elif name == 'submit':
                    text, error = submit(arguments)
                else:
                    text, error = f'Unknown tool: {name}', True
            except Exception as failure:  # Reported to the brain as a failed tool call.
                text, error = f'The tool failed: {failure}', True
        self.write({'jsonrpc': '2.0', 'id': request_id, 'result': {'content': [{'type': 'text', 'text': text}], 'isError': error}})

    def serve(self):
        for line in sys.stdin:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            method, request_id = message.get('method'), message.get('id')
            if method is None or request_id is None:
                continue  # A notification or a response.
            if method == 'initialize':
                version = (message.get('params') or {}).get('protocolVersion') or '2025-06-18'
                self.write({'jsonrpc': '2.0', 'id': request_id, 'result': {
                    'protocolVersion': version, 'capabilities': {'tools': {}},
                    'serverInfo': {'name': 'worker', 'version': '0.1.0'},
                }})
            elif method == 'tools/list':
                self.write({'jsonrpc': '2.0', 'id': request_id, 'result': {'tools': TOOLS}})
            elif method == 'tools/call':
                threading.Thread(target=self.call_tool, args=(request_id, message.get('params') or {}), daemon=True).start()
            elif method == 'ping':
                self.write({'jsonrpc': '2.0', 'id': request_id, 'result': {}})
            else:
                self.write({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32601, 'message': f'unknown method {method}'}})


if __name__ == '__main__':
    Server().serve()
