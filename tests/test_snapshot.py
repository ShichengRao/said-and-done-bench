"""Snapshots are taken with the agent's container frozen, so late writes can't get in."""

import asyncio
import tarfile
import uuid

from beambench.container import Container
from beambench.snapshot import snapshot_workspace
from tests.task_helpers import docker


@docker
def test_a_background_write_after_the_pause_is_not_in_the_snapshot(tmp_path):
  workspace = tmp_path / 'workspace'
  workspace.mkdir()
  container = Container(
    image='beambench-task:dev', name=f'beambench-test-{uuid.uuid4().hex[:8]}',
    mounts=[(workspace, '/workspace')], networks=['none'],
  )

  async def scenario():
    await container.start()
    try:
      # A "fix" that lands half a second after the agent submits.
      await container.output(['sh', '-c', "(sleep 0.5; echo fixed > /workspace/fix.txt) >/dev/null 2>&1 &"])
      assert await container.pause()
      await asyncio.sleep(1.5)  # Longer than the background command needs.
      snapshot = snapshot_workspace(workspace, tmp_path / 'snapshot.tar.gz')
      await container.unpause()
      await asyncio.sleep(1.0)
      return snapshot
    finally:
      await container.remove()

  asyncio.run(scenario())
  with tarfile.open(tmp_path / 'snapshot.tar.gz') as tar:
    assert 'workspace/fix.txt' not in tar.getnames()
  assert (workspace / 'fix.txt').read_text() == 'fixed\n'  # It ran once unfrozen, after the snapshot.
