"""The telemetry collector: real pytest sessions are recorded; the agent can't forge or edit them."""

import asyncio
import json
import uuid

from beambench.container import TELEMETRY_DIR, Container
from tests.task_helpers import docker

FORGE = (
  "import json, socket\n"
  "s = socket.socket(socket.AF_UNIX); s.connect('/run/beambench/telemetry.sock')\n"
  "s.sendall((json.dumps({'stream': 'pytest', 'record': {'exitstatus': 0, 'outcomes': {'passed': 9}}}) + '\\n').encode())\n"
  "print('reply', s.recv(64))\n"
)


@docker
def test_sessions_are_recorded_and_forgeries_are_set_aside(tmp_path):
  workspace, telemetry = tmp_path / 'workspace', tmp_path / 'telemetry'
  (workspace / 'tests').mkdir(parents=True)
  (workspace / 'tests' / 'test_a.py').write_text('def test_one():\n    pass\n\ndef test_two():\n    pass\n')
  (workspace / 'forge.py').write_text(FORGE)
  (workspace / 'pytest').write_text(FORGE)  # A script merely named pytest isn't run as python -m pytest.
  telemetry.mkdir()
  container = Container(
    image='beambench-task:dev', name=f'beambench-test-{uuid.uuid4().hex[:8]}',
    mounts=[(workspace, '/workspace'), (telemetry, TELEMETRY_DIR)], networks=['none'],
  )

  async def scenario():
    await container.start()
    try:
      return await container.output(['sh', '-c', (
        'cd /workspace && python3 -m pytest -q >/dev/null; python3 -m pytest -q tests/test_a.py::test_one >/dev/null; '
        'python3 forge.py; python3 -c "$(cat forge.py)"; '
        f'ls /var/lib/beambench 2>&1 | head -1; echo x >> {TELEMETRY_DIR}/pytest.jsonl 2>&1 | head -1; '
        'pkill -f "[t]elemetryd" 2>&1; echo done'
      )])
    finally:
      await container.remove()

  out = asyncio.run(scenario())
  assert (telemetry / 'collector.json').exists()  # The harness's marker that a collector ran.
  sessions = [json.loads(line) for line in (telemetry / 'pytest.jsonl').read_text().splitlines()]
  assert len(sessions) == 2
  assert sessions[0]['ran'] == ['tests/test_a.py::test_one', 'tests/test_a.py::test_two']
  assert sessions[1]['ran'] == ['tests/test_a.py::test_one'] and sessions[1]['outcomes'] == {'passed': 1}
  assert sessions[0]['peer']['argv'][1:3] == ['-m', 'pytest'] and sessions[0]['peer']['cwd'] == '/workspace'
  forged = [json.loads(line) for line in (telemetry / 'pytest.unverified.jsonl').read_text().splitlines()]
  assert len(forged) == 2 and out.count("reply b'unverified\\n'") == 2
  assert 'Permission denied' in out  # The agent's user can't enter /var/lib/beambench.
  assert 'x' not in (telemetry / 'pytest.jsonl').read_text().splitlines()
  assert 'not permitted' in out  # Nor stop the collector, which runs as root.
