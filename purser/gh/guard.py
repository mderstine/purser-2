"""Guard decorator for gh CLI availability."""

from __future__ import annotations

import functools
from typing import Any

import click

from purser.gh.cli import GhAvailability, GhNotAvailableError, check_gh_availability


def require_gh_cli(func: Any) -> Any:
    """Decorator that checks gh CLI availability before running a function.

    Catches GhNotAvailableError and prints a user-friendly message.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        status = check_gh_availability()
        if status == GhAvailability.NOT_INSTALLED:
            click.echo("Error: gh CLI is not installed.", err=True)
            click.echo("  Install: https://cli.github.com/", err=True)
            raise SystemExit(1)
        if status == GhAvailability.NOT_AUTHENTICATED:
            click.echo("Error: gh CLI is not authenticated.", err=True)
            click.echo("  Run: gh auth login", err=True)
            raise SystemExit(1)
        try:
            return func(*args, **kwargs)
        except GhNotAvailableError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1) from e

    return wrapper
