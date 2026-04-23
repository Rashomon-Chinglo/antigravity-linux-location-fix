"""Unified subprocess wrapper. All shell commands go through here.

Provides two entry points:
- ``run``: for write operations — skipped under ``dry_run``.
- ``run_read``: for read-only operations — always executes.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

from ag_warp.ui import console


@dataclass
class Shell:
    """Thin wrapper around :func:`subprocess.run`.

    When *dry_run* is ``True``, write operations are printed but not executed.
    """

    dry_run: bool = False
    _log: list[list[str]] = field(default_factory=list, repr=False)

    # -- write operations (skipped in dry-run) --------------------------------

    def run(
        self,
        cmd: list[str],
        *,
        check: bool = True,
        capture: bool = True,
        input_text: str | None = None,
        desc: str = "",
    ) -> subprocess.CompletedProcess[str]:
        """Execute a write command. Skipped when *dry_run* is ``True``."""
        if self.dry_run:
            label = desc or " ".join(cmd)
            console.print(f"  [dim]dry-run:[/dim] {label}")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        self._log.append(cmd)
        return self._execute(
            cmd,
            check=check,
            capture=capture,
            input_text=input_text,
        )

    # -- read operations (always execute) -------------------------------------

    def run_read(
        self,
        cmd: list[str],
        *,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a read-only command. Runs even in dry-run mode."""
        return self._execute(cmd, check=check, capture=True)

    # -- helpers --------------------------------------------------------------

    def _execute(
        self,
        cmd: list[str],
        *,
        check: bool,
        capture: bool,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess and surface stderr when ``check=True`` fails."""
        try:
            return subprocess.run(
                cmd,
                check=check,
                capture_output=capture,
                text=True,
                input=input_text,
            )
        except subprocess.CalledProcessError as exc:
            self._print_failure(exc)
            raise

    def _print_failure(self, exc: subprocess.CalledProcessError) -> None:
        """Print a concise command failure summary before re-raising."""
        console.print(
            f"[red]✗ Command failed ({exc.returncode}): {' '.join(map(str, exc.cmd))}[/red]"
        )
        stderr = (exc.stderr or "").strip()
        if stderr:
            console.print(f"[red]{stderr}[/red]")

    def has_command(self, name: str) -> bool:
        """Return ``True`` if *name* is available on ``$PATH``."""
        return self.resolve_command(name) is not None

    def resolve_command(self, name: str) -> str | None:
        """Return the resolved executable path for *name*, if available."""
        return shutil.which(name)
