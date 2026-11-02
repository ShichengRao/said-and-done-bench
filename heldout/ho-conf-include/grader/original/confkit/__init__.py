"""confkit: the config file format our services share (see docs/format.md)."""

from confkit.errors import ConfigError
from confkit.parser import load, parse

__all__ = ['ConfigError', 'load', 'parse']
