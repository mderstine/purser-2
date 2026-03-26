"""Purser: Agent-agnostic project management framework."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("purser")
except PackageNotFoundError:
    __version__ = "0.1.0-dev"
