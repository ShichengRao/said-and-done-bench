"""Workspace snapshots taken at a run's terminal outcome."""

from __future__ import annotations

import tarfile
from pathlib import Path

from beambench.outcomes import utc_now


def snapshot_workspace(workspace: Path, destination: Path) -> dict:
  """Write the workspace to a gzipped tarball. Symlinks are stored, not followed."""
  taken_at = utc_now()
  with tarfile.open(destination, 'w:gz') as tar:
    tar.add(workspace, arcname='workspace')
  return {
    'file': destination.name,
    'bytes': destination.stat().st_size,
    'taken_at': taken_at,
  }
