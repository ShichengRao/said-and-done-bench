"""Offline multi-repository package installer with signed trust metadata."""
from installer.api import install
from installer.store import initialize, inspect

__all__ = ['initialize', 'inspect', 'install']
