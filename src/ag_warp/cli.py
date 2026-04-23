"""ag-warp CLI — the single entry point for all operations."""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ag_warp import __version__
from ag_warp.config import AppConfig, load_config
from ag_warp.discovery import (
    discover_latest,
    discover_versions,
)
from ag_warp.shell import Shell

console = Console(stderr=True)

app = typer.Typer(
    name="ag-warp",
    help=(
        'Fix for "User location is not supported for the API use." '
        "on Linux VPS. GID-based nftables transparent proxy through "
        "Cloudflare WARP."
    ),
    no_args_is_help=True,
    add_completion=False,
)

# -- shared options ------------------------------------------------------------

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

LOCK_PATH = Path("/var/run/ag-warp.lock")

# Exit codes.
EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_CONFIG_ERROR = 2
EXIT_DEPENDENCY_MISSING = 3
EXIT_USER_CANCELLED = 4


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


# -- helpers -------------------------------------------------------------------


def _load(config_path: Path | None) -> AppConfig:
    try:
        return load_config(config_path)
    except Exception as exc:
        console.print(f"[red]✗ Config error: {exc}[/red]")
        raise SystemExit(EXIT_CONFIG_ERROR)


def _resolve_gid(group_name: str, shell: Shell) -> int | None:
    r = shell.run_read(["getent", "group", group_name])
    if r.returncode != 0:
        return None
    parts = r.stdout.strip().split(":")
    return int(parts[2]) if len(parts) >= 3 else None


def _ensure_group(group_name: str, shell: Shell) -> int:
    gid = _resolve_gid(group_name, shell)
    if gid is not None:
        return gid
    console.print(f"  Creating group {group_name} …")
    shell.run(["groupadd", "--system", group_name])
    gid = _resolve_gid(group_name, shell)
    if gid is None:
        console.print(f"[red]✗ Failed to create group {group_name}[/red]")
        raise SystemExit(EXIT_FAILURE)
    return gid


def _is_antigravity_running(shell: Shell) -> bool:
    r = shell.run_read(["pgrep", "-f", "antigravity-server"])
    return r.returncode == 0


def _print_restart_notice(shell: Shell) -> None:
    if _is_antigravity_running(shell):
        console.print()
        console.print(
            "[yellow]⚠  Antigravity is currently running. "
            "Restart required: reload the Antigravity Remote SSH window.[/yellow]"
        )


# -- commands ------------------------------------------------------------------


@app.command()
def status(
    config: ConfigOption = None,
) -> None:
    """Read-only status check of all components."""
    from ag_warp import nftables as nft_mod
    from ag_warp import supervisor as sv_mod
    from ag_warp import warp as warp_mod

    cfg = _load(config)
    shell = Shell(dry_run=False)

    console.print("[bold]ag-warp status[/bold]")
    console.print()

    # WARP.
    ws = warp_mod.get_status(shell)
    _status_line("WARP proxy", ws.connected, f"mode={ws.mode} port={ws.proxy_port}")

    # sing-box.
    sb_running = sv_mod.is_running(cfg, shell)
    sb_label = (
        cfg.singbox.service_name
        if cfg.supervisor.backend == "systemd"
        else cfg.singbox.pm2_app_name
    )
    _status_line(
        f"sing-box ({cfg.supervisor.backend})",
        sb_running,
        sb_label,
    )

    # nftables.
    nft_ok = nft_mod.table_exists(cfg.nftables, shell)
    _status_line(
        "nftables",
        nft_ok,
        f"{cfg.nftables.table_family} {cfg.nftables.table_name}",
    )

    # Antigravity versions.
    console.print()
    versions = discover_versions(cfg.antigravity_base_dir)
    if not versions:
        console.print("  [yellow]No Antigravity versions found.[/yellow]")
    else:
        table = Table(show_header=True, box=None, pad_edge=False)
        table.add_column("Version", style="cyan")
        table.add_column("Status")
        table.add_column("Note")
        for v in versions:
            ws_icon = {
                "wrapped": "[green]wrapped[/green]",
                "unwrapped": "[yellow]unwrapped[/yellow]",
                "stale": "[red]stale[/red]",
                "unknown": "[red]unknown[/red]",
            }.get(v.wrapper_status, v.wrapper_status)
            note = "LATEST" if v is versions[0] else ""
            table.add_row(v.version[:40], ws_icon, note)
        console.print(table)

    latest = versions[0] if versions else None
    if latest and latest.wrapper_status == "unwrapped":
        console.print()
        console.print(
            f"  [yellow]Detected unwrapped Antigravity version: {latest.version[:40]}[/yellow]"
        )
        console.print("  Suggested: [bold]ag-warp on[/bold]")

    # Warn if wrapper active but nftables missing.
    if latest and latest.wrapper_status == "wrapped" and not nft_ok:
        console.print()
        console.print(
            "  [yellow]⚠ Wrapper is active but nftables is not applied.[/yellow]\n"
            "    Traffic is NOT being routed through WARP.\n"
            "    Run [bold]ag-warp on[/bold] to re-enable, or "
            "[bold]ag-warp rollback[/bold] to fully remove."
        )

    # cloudflared.
    console.print()
    cf_r = shell.run_read(["pgrep", "-x", "cloudflared"])
    cf_installed = shell.has_command("cloudflared")
    if cf_r.returncode == 0:
        cf_detail = "running"
    elif not cf_installed:
        cf_detail = "not installed"
    else:
        cf_detail = "not running"
    _status_line(
        "cloudflared",
        cf_r.returncode == 0 or not cf_installed,
        cf_detail,
    )


def _status_line(label: str, ok: bool, detail: str) -> None:
    icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
    console.print(f"  {icon} {label}: {detail}")


@app.command(name="on")
def on_cmd(
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
    yes: YesOption = False,
    skip_wrapper: Annotated[
        bool,
        typer.Option("--skip-wrapper", help="Skip wrapper injection (for restore service)."),
    ] = False,
) -> None:
    """Start and converge all components to desired state."""
    from ag_warp import docker as docker_mod
    from ag_warp import nftables as nft_mod
    from ag_warp import singbox as sb_mod
    from ag_warp import supervisor as sv_mod
    from ag_warp import warp as warp_mod
    from ag_warp import wrapper as wrapper_mod
    from ag_warp.state import append_change, load_state, save_state

    cfg = _load(config)
    shell = Shell(dry_run=dry_run)

    with _acquire_lock():
        console.print("[bold]ag-warp on[/bold]" + (" [dim](dry-run)[/dim]" if dry_run else ""))
        console.print()

        # 1. Doctor check.
        if not _doctor_check(cfg, shell):
            raise SystemExit(EXIT_DEPENDENCY_MISSING)

        # 2. Ensure group.
        gid = _ensure_group(cfg.group_name, shell)
        console.print(f"  [green]✓[/green] Group {cfg.group_name} (gid {gid})")

        # 3. WARP proxy.
        warp_changed = warp_mod.ensure_proxy_mode(cfg.warp, shell)
        console.print(
            f"  [green]✓[/green] WARP proxy on :{cfg.warp.proxy_port}"
            f"{' — configured' if warp_changed else ' — already active'}"
        )

        # 4. sing-box config.
        sb_changed = sb_mod.ensure_config(cfg.singbox, cfg.warp, dry_run=dry_run)
        console.print(
            f"  [green]✓[/green] sing-box config {cfg.singbox.config_path}"
            f"{' — updated' if sb_changed else ' — unchanged'}"
        )

        # 5. sing-box service.
        sv_changed = sv_mod.ensure_running(cfg, shell, config_changed=sb_changed)
        console.print(
            f"  [green]✓[/green] sing-box service ({cfg.supervisor.backend})"
            f"{' — started/restarted' if sv_changed else ' — already running'}"
        )

        # 6. Docker bridge CIDRs.
        docker_cidrs: list[str] = []
        if cfg.nftables.auto_detect_docker_bridges:
            docker_cidrs = docker_mod.discover_docker_cidrs(shell)
            if docker_cidrs:
                console.print(f"  [green]✓[/green] Docker bridges: {', '.join(docker_cidrs)}")

        # 7–8. nftables.
        nft_mod.apply_rules(cfg.nftables, gid, cfg.singbox.listen_port, shell, docker_cidrs)
        console.print(
            f"  [green]✓[/green] nftables table {cfg.nftables.table_family} "
            f"{cfg.nftables.table_name}"
        )

        # 9–11. Wrapper.
        state = load_state(cfg.state_file)
        if not skip_wrapper:
            latest = discover_latest(
                cfg.antigravity_base_dir,
                cfg.pin_version,
            )
            if latest is None:
                console.print(
                    "  [yellow]⚠ No Antigravity version found. Skipping wrapper.[/yellow]"
                )
            elif latest.wrapper_status == "unwrapped":
                if not yes:
                    proceed = typer.confirm(
                        f"  Inject wrapper into {latest.server_binary}?",
                        default=False,
                    )
                    if not proceed:
                        console.print("  Skipped wrapper injection.")
                        _print_restart_notice(shell)
                        raise SystemExit(EXIT_USER_CANCELLED)

                meta = wrapper_mod.inject_wrapper(latest, cfg.group_name, shell)
                append_change(state, "wrapper", "wrapped", rollback_safe=True, **meta)
                console.print(f"  [green]✓[/green] Wrapper injected: {latest.version[:40]}")
            elif latest.wrapper_status == "wrapped":
                console.print(f"  [green]✓[/green] Wrapper already active: {latest.version[:40]}")
            else:
                console.print(
                    f"  [yellow]⚠ Wrapper status is '{latest.wrapper_status}'. "
                    f"Manual inspection required.[/yellow]"
                )
        else:
            console.print("  [dim]Skipped wrapper (--skip-wrapper)[/dim]")

        # 12. Save state.
        if not dry_run:
            save_state(cfg.state_file, state)

        # 13. Restart notice.
        _print_restart_notice(shell)

        console.print()
        console.print("[green]Done.[/green]")


@app.command()
def apply(
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
    yes: YesOption = False,
    skip_wrapper: Annotated[
        bool,
        typer.Option("--skip-wrapper", help="Skip wrapper injection."),
    ] = False,
) -> None:
    """Alias for 'on'."""
    on_cmd(config=config, dry_run=dry_run, yes=yes, skip_wrapper=skip_wrapper)


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
    from ag_warp import nftables as nft_mod
    from ag_warp import supervisor as sv_mod

    cfg = _load(config)
    shell = Shell(dry_run=dry_run)

    with _acquire_lock():
        console.print("[bold]ag-warp off[/bold]" + (" [dim](dry-run)[/dim]" if dry_run else ""))
        console.print()

        # 1. Stop sing-box.
        sv_mod.stop_service(cfg, shell)
        console.print("  [green]✓[/green] sing-box stopped")

        # 2. Remove nftables.
        nft_mod.remove_rules(cfg.nftables, shell)
        console.print("  [green]✓[/green] nftables removed")

        # 3. Optionally disconnect WARP.
        if disconnect_warp:
            shell.run(["warp-cli", "--accept-tos", "disconnect"], check=False)
            console.print("  [green]✓[/green] WARP disconnected")

        console.print()
        console.print("[dim]Wrapper and state preserved. Use 'rollback' to fully restore.[/dim]")
        _print_restart_notice(shell)


@app.command()
def rollback(
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
    yes: YesOption = False,
) -> None:
    """Full rollback: off + safe wrapper restore."""
    from ag_warp import wrapper as wrapper_mod
    from ag_warp.state import get_latest_change, load_state

    cfg = _load(config)
    shell = Shell(dry_run=dry_run)

    with _acquire_lock():
        dry_label = " [dim](dry-run)[/dim]" if dry_run else ""
        console.print(f"[bold]ag-warp rollback[/bold]{dry_label}")
        console.print()

        if not yes:
            proceed = typer.confirm(
                "  This will stop interception and restore the original binary. Continue?",
                default=False,
            )
            if not proceed:
                raise SystemExit(EXIT_USER_CANCELLED)

        # 1. Run off.
        off(config=config, dry_run=dry_run, yes=True)
        console.print()

        # 2. Safe wrapper restore.
        state = load_state(cfg.state_file)
        latest_wrapper = get_latest_change(state, "wrapper")
        expected_sha = None
        if latest_wrapper:
            # Access extra fields via model_extra (Pydantic v2 extra="allow").
            extra = latest_wrapper.model_extra or {}
            expected_sha = extra.get("wrapper_sha256")

        latest = discover_latest(
            cfg.antigravity_base_dir,
            cfg.pin_version,
        )
        if latest is None:
            console.print(
                "  [yellow]⚠ No Antigravity version found. Skipping wrapper restore.[/yellow]"
            )
        else:
            restored = wrapper_mod.safe_restore(latest, expected_sha, shell)
            if restored:
                console.print(f"  [green]✓[/green] Original binary restored: {latest.version[:40]}")
            else:
                console.print()
                console.print("  [yellow]Manual inspection may be required:[/yellow]")
                console.print(f"    ls -la {latest.bin_dir}/antigravity-server*")

        _print_restart_notice(shell)
        console.print()
        console.print("[green]Rollback complete.[/green]")


@app.command()
def verify(
    config: ConfigOption = None,
) -> None:
    """End-to-end routing verification."""
    from ag_warp.verify import print_results, run_verify

    cfg = _load(config)
    shell = Shell(dry_run=False)

    console.print("[bold]ag-warp verify[/bold]")
    console.print()

    results = run_verify(cfg, shell)
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
) -> None:
    """Print the final merged configuration."""
    cfg = _load(config)
    console.print(json.dumps(cfg.model_dump(mode="json"), indent=2, default=str))


@app.command()
def doctor(
    config: ConfigOption = None,
) -> None:
    """Check system dependencies."""
    cfg = _load(config)
    shell = Shell(dry_run=False)

    console.print("[bold]ag-warp doctor[/bold]")
    console.print()

    ok = _doctor_check(cfg, shell, verbose=True)
    console.print()
    if ok:
        console.print("[green]All dependencies present.[/green]")
    else:
        console.print("[red]Missing dependencies. Install them before running 'ag-warp on'.[/red]")
        raise SystemExit(EXIT_DEPENDENCY_MISSING)


def _doctor_check(cfg: AppConfig, shell: Shell, verbose: bool = False) -> bool:
    """Check that required system commands exist."""
    required = ["warp-cli", "sing-box", "nft", "setpriv", "curl", "ss", "ps", "getent"]

    if cfg.supervisor.backend == "systemd":
        required.append("systemctl")
    else:
        required.append("pm2")

    optional = ["docker", "cloudflared"]

    all_ok = True
    for cmd in required:
        found = shell.has_command(cmd)
        if verbose:
            icon = "[green]✓[/green]" if found else "[red]✗[/red]"
            console.print(f"  {icon} {cmd}" + ("" if found else " [red](REQUIRED)[/red]"))
        if not found:
            all_ok = False

    if verbose:
        for cmd in optional:
            found = shell.has_command(cmd)
            icon = "[green]✓[/green]" if found else "[dim]○[/dim]"
            console.print(f"  {icon} {cmd}" + ("" if found else " (optional)"))

    return all_ok


@app.callback()
def _main(
    version: Annotated[
        bool,
        typer.Option("--version", "-V", help="Show version and exit."),
    ] = False,
) -> None:
    if version:
        console.print(f"ag-warp {__version__}")
        raise typer.Exit()
