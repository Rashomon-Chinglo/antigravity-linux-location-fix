"""Shared Rich console helpers."""

from __future__ import annotations

from rich.console import Console

console = Console(stderr=True)


def render_command_header(command: str, *, dry_run: bool = False) -> str:
    """Render a consistent command header across CLI entry points."""
    header = f"[bold]{command}[/bold]"
    if dry_run:
        return f"{header} [dim](dry-run)[/dim]"
    return header
