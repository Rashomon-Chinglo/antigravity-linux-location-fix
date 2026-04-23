"""ag-warp CLI — thin argument-parsing layer.

All business logic lives in :mod:`ag_warp.engine`.
This module only handles:
    1. Typer command/option definitions
    2. Config loading with CLI overrides
    3. flock-based concurrency guard
    4. Delegating to engine functions
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from ag_warp import __version__
from ag_warp.config import AppConfig, load_config
from ag_warp.engine import (
    OffOptions,
    OnOptions,
    RollbackOptions,
    run_off,
    run_on,
    run_rollback,
    run_status,
)
from ag_warp.shell import Shell
from ag_warp.system import doctor_check
from ag_warp.ui import console, render_command_header
from ag_warp.verify import print_results, run_verify

app = typer.Typer(
    name="ag-warp",
    help=(
        'Fix for "User location is not supported for the API use." '
        "on Linux VPS. GID-based nftables transparent proxy through "
        "Cloudflare WARP."
    ),
    invoke_without_command=True,
    add_completion=False,
)

# -- reusable option types -----------------------------------------------------

ConfigOption = Annotated[
    Path | None,
    typer.Option("--config", "-c", help="Path to config.json override."),
]
DryRunOption = Annotated[
    bool,
    typer.Option("--dry-run", help="Print planned changes without executing."),
]
YesOption = Annotated[
    bool,
    typer.Option("--yes", "-y", help="Skip interactive confirmations."),
]
WarpPortOption = Annotated[
    int | None,
    typer.Option(
        "--warp-port",
        help="Override WARP proxy port (default: 40000).",
    ),
]
SingboxPortOption = Annotated[
    int | None,
    typer.Option(
        "--singbox-port",
        help="Override sing-box listen port (default: 12345).",
    ),
]

LOCK_PATH = Path("/var/run/ag-warp.lock")

# Exit codes.
EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_CONFIG_ERROR = 2
EXIT_DEPENDENCY_MISSING = 3
EXIT_USER_CANCELLED = 4


@dataclass(frozen=True)
class CommandRuntime:
    """Fully built runtime objects shared by CLI command handlers."""

    config: AppConfig
    shell: Shell


# -- lock ----------------------------------------------------------------------


@contextmanager
def _acquire_lock() -> Iterator[None]:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        console.print("[red]✗ Another ag-warp instance is running.[/red]")
        raise SystemExit(EXIT_FAILURE)
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# -- config loading helper ----------------------------------------------------


def _load(
    config_path: Path | None,
    *,
    warp_port: int | None = None,
    singbox_port: int | None = None,
) -> AppConfig:
    """Build ``AppConfig`` from file + CLI overrides."""
    try:
        return load_config(
            config_path,
            cli_overrides=_build_cli_overrides(
                warp_port=warp_port,
                singbox_port=singbox_port,
            ),
        )
    except Exception as exc:
        console.print(f"[red]✗ Config error: {exc}[/red]")
        raise SystemExit(EXIT_CONFIG_ERROR)


def _build_cli_overrides(
    *,
    warp_port: int | None,
    singbox_port: int | None,
) -> dict[str, Any] | None:
    """Translate CLI flags into dotted-path config overrides."""
    overrides: dict[str, Any] = {}
    if warp_port is not None:
        overrides["warp.proxy_port"] = warp_port
    if singbox_port is not None:
        overrides["singbox.listen_port"] = singbox_port
    return overrides or None


def _build_runtime(
    *,
    config_path: Path | None,
    dry_run: bool,
    warp_port: int | None = None,
    singbox_port: int | None = None,
) -> CommandRuntime:
    """Build the shared runtime objects used by command handlers."""
    return CommandRuntime(
        config=_load(
            config_path,
            warp_port=warp_port,
            singbox_port=singbox_port,
        ),
        shell=Shell(dry_run=dry_run),
    )


# -- commands ------------------------------------------------------------------


@app.command()
def status(
    config: ConfigOption = None,
    warp_port: WarpPortOption = None,
    singbox_port: SingboxPortOption = None,
) -> None:
    """Read-only status check of all components."""
    runtime = _build_runtime(
        config_path=config,
        dry_run=False,
        warp_port=warp_port,
        singbox_port=singbox_port,
    )
    run_status(runtime.config, runtime.shell)


@app.command(name="on")
def on_cmd(
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
    yes: YesOption = False,
    skip_wrapper: Annotated[
        bool,
        typer.Option(
            "--skip-wrapper",
            help="Skip wrapper injection (for restore service).",
        ),
    ] = False,
    warp_port: WarpPortOption = None,
    singbox_port: SingboxPortOption = None,
) -> None:
    """Start and converge all components to desired state."""
    runtime = _build_runtime(
        config_path=config,
        dry_run=dry_run,
        warp_port=warp_port,
        singbox_port=singbox_port,
    )
    with _acquire_lock():
        run_on(
            runtime.config,
            runtime.shell,
            OnOptions(
                dry_run=dry_run,
                yes=yes,
                skip_wrapper=skip_wrapper,
            ),
        )


@app.command()
def apply(
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
    yes: YesOption = False,
    skip_wrapper: Annotated[
        bool,
        typer.Option("--skip-wrapper", help="Skip wrapper injection."),
    ] = False,
    warp_port: WarpPortOption = None,
    singbox_port: SingboxPortOption = None,
) -> None:
    """Alias for 'on'."""
    on_cmd(
        config=config,
        dry_run=dry_run,
        yes=yes,
        skip_wrapper=skip_wrapper,
        warp_port=warp_port,
        singbox_port=singbox_port,
    )


@app.command()
def off(
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
    yes: YesOption = False,
    disconnect_warp: Annotated[
        bool,
        typer.Option("--disconnect-warp", help="Also disconnect WARP."),
    ] = False,
) -> None:
    """Stop runtime interception (keep wrapper, keep state)."""
    runtime = _build_runtime(config_path=config, dry_run=dry_run)
    with _acquire_lock():
        run_off(
            runtime.config,
            runtime.shell,
            OffOptions(
                dry_run=dry_run,
                disconnect_warp=disconnect_warp,
            ),
        )


@app.command()
def rollback(
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
    yes: YesOption = False,
) -> None:
    """Full rollback: off + safe wrapper restore."""
    runtime = _build_runtime(config_path=config, dry_run=dry_run)
    with _acquire_lock():
        run_rollback(
            runtime.config,
            runtime.shell,
            RollbackOptions(
                dry_run=dry_run,
                yes=yes,
            ),
        )


@app.command()
def verify(
    config: ConfigOption = None,
    warp_port: WarpPortOption = None,
    singbox_port: SingboxPortOption = None,
) -> None:
    """End-to-end routing verification."""
    runtime = _build_runtime(
        config_path=config,
        dry_run=False,
        warp_port=warp_port,
        singbox_port=singbox_port,
    )

    console.print(f"{render_command_header('ag-warp verify')}\n")
    results = run_verify(runtime.config, runtime.shell)
    all_ok = print_results(results)

    console.print()
    if all_ok:
        console.print("[green]All checks passed.[/green]")
    else:
        console.print("[red]Some checks failed.[/red]")
        raise SystemExit(EXIT_FAILURE)


@app.command(name="dump-config")
def dump_config(
    config: ConfigOption = None,
    warp_port: WarpPortOption = None,
    singbox_port: SingboxPortOption = None,
) -> None:
    """Print the final merged configuration."""
    runtime = _build_runtime(
        config_path=config,
        dry_run=False,
        warp_port=warp_port,
        singbox_port=singbox_port,
    )
    console.print(
        json.dumps(runtime.config.model_dump(mode="json"), indent=2, default=str),
    )


@app.command()
def doctor(config: ConfigOption = None) -> None:
    """Check system dependencies."""
    runtime = _build_runtime(config_path=config, dry_run=False)

    console.print(f"{render_command_header('ag-warp doctor')}\n")
    ok = doctor_check(runtime.config, runtime.shell, verbose=True)

    console.print()
    if ok:
        console.print("[green]All dependencies present.[/green]")
    else:
        console.print("[red]Missing dependencies. Install them before running 'ag-warp on'.[/red]")
        raise SystemExit(EXIT_DEPENDENCY_MISSING)


# -- callback (--version / no-command) ----------------------------------------


@app.callback()
def _main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", "-V", help="Show version and exit."),
    ] = False,
) -> None:
    if version:
        console.print(f"ag-warp {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()
