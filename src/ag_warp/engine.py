"""Core orchestration engine — the business logic behind each CLI command.

``cli.py`` handles argument parsing; this module handles *what actually happens*.
Each public function takes an ``AppConfig``, a ``Shell``, and behavioural flags,
then executes the corresponding workflow.
"""

from __future__ import annotations

from dataclasses import dataclass

import typer
from rich.console import Console
from rich.table import Table

from ag_warp import docker as docker_mod
from ag_warp import nftables as nft_mod
from ag_warp import singbox as sb_mod
from ag_warp import supervisor as sv_mod
from ag_warp import warp as warp_mod
from ag_warp import wrapper as wrapper_mod
from ag_warp.config import AppConfig
from ag_warp.discovery import discover_latest, discover_versions
from ag_warp.shell import Shell
from ag_warp.state import append_change, get_latest_change, load_state, save_state
from ag_warp.system import (
    check_port_availability,
    doctor_check,
    ensure_group,
    is_antigravity_running,
)

console = Console(stderr=True)


# -- shared output helpers ----------------------------------------------------


def _ok(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}")


def _warn(msg: str) -> None:
    console.print(f"  [yellow]⚠[/yellow] {msg}")


def _fail(msg: str) -> None:
    console.print(f"  [red]✗[/red] {msg}")


def _print_restart_notice(shell: Shell) -> None:
    if is_antigravity_running(shell):
        console.print()
        console.print(
            "[yellow]⚠  Antigravity is currently running. "
            "Restart required: reload the Antigravity Remote SSH window.[/yellow]"
        )


# -- status -------------------------------------------------------------------


def run_status(cfg: AppConfig, shell: Shell) -> None:
    """Read-only status check of all components."""
    console.print("[bold]ag-warp status[/bold]\n")

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
    _status_line(f"sing-box ({cfg.supervisor.backend})", sb_running, sb_label)

    # nftables.
    nft_ok = nft_mod.table_exists(cfg.nftables, shell)
    _status_line(
        "nftables",
        nft_ok,
        f"{cfg.nftables.table_family} {cfg.nftables.table_name}",
    )

    # Antigravity versions.
    _print_versions(cfg, nft_ok)

    # cloudflared.
    _print_cloudflared(shell)


def _status_line(label: str, ok: bool, detail: str) -> None:
    icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
    console.print(f"  {icon} {label}: {detail}")


def _print_versions(cfg: AppConfig, nft_ok: bool) -> None:
    console.print()
    versions = discover_versions(cfg.antigravity_base_dir)
    if not versions:
        console.print("  [yellow]No Antigravity versions found.[/yellow]")
        return

    table = Table(show_header=True, box=None, pad_edge=False)
    table.add_column("Version", style="cyan")
    table.add_column("Status")
    table.add_column("Note")
    status_style = {
        "wrapped": "[green]wrapped[/green]",
        "unwrapped": "[yellow]unwrapped[/yellow]",
        "stale": "[red]stale[/red]",
        "unknown": "[red]unknown[/red]",
    }
    for v in versions:
        ws_icon = status_style.get(v.wrapper_status, v.wrapper_status)
        note = "LATEST" if v is versions[0] else ""
        table.add_row(v.version[:40], ws_icon, note)
    console.print(table)

    latest = versions[0]
    if latest.wrapper_status == "unwrapped":
        console.print()
        console.print(f"  [yellow]Detected unwrapped version: {latest.version[:40]}[/yellow]")
        console.print("  Suggested: [bold]ag-warp on[/bold]")

    if latest.wrapper_status == "wrapped" and not nft_ok:
        console.print()
        console.print(
            "  [yellow]⚠ Wrapper is active but nftables not applied.[/yellow]\n"
            "    Traffic is NOT routed through WARP.\n"
            "    Run [bold]ag-warp on[/bold] to re-enable, "
            "or [bold]ag-warp rollback[/bold] to fully remove."
        )


def _print_cloudflared(shell: Shell) -> None:
    console.print()
    cf_running = shell.run_read(["pgrep", "-x", "cloudflared"]).returncode == 0
    cf_installed = shell.has_command("cloudflared")
    if cf_running:
        detail = "running"
    elif not cf_installed:
        detail = "not installed"
    else:
        detail = "not running"
    _status_line("cloudflared", cf_running or not cf_installed, detail)


# -- on (apply) ---------------------------------------------------------------


@dataclass
class OnOptions:
    """Behavioural flags for :func:`run_on`."""

    dry_run: bool = False
    yes: bool = False
    skip_wrapper: bool = False


def run_on(cfg: AppConfig, shell: Shell, opts: OnOptions) -> None:
    """Start and converge all components to desired state."""
    label = "[bold]ag-warp on[/bold]"
    if opts.dry_run:
        label += " [dim](dry-run)[/dim]"
    console.print(f"{label}\n")

    # 1. Doctor.
    if not doctor_check(cfg, shell):
        raise SystemExit(3)

    # 2. Port pre-check.
    port_errors = check_port_availability(
        cfg.warp.proxy_port,
        cfg.singbox.listen_port,
        shell,
    )
    for err in port_errors:
        _fail(err)
    if port_errors:
        raise SystemExit(1)

    # 3. Group.
    gid = ensure_group(cfg.group_name, shell)
    _ok(f"Group {cfg.group_name} (gid {gid})")

    # 4. WARP proxy.
    warp_changed = warp_mod.ensure_proxy_mode(cfg.warp, shell)
    _ok(
        f"WARP proxy on :{cfg.warp.proxy_port}"
        f"{' — configured' if warp_changed else ' — already active'}"
    )

    # 5. sing-box config.
    sb_changed = sb_mod.ensure_config(
        cfg.singbox,
        cfg.warp,
        dry_run=opts.dry_run,
    )
    _ok(
        f"sing-box config {cfg.singbox.config_path}{' — updated' if sb_changed else ' — unchanged'}"
    )

    # 6. sing-box service.
    sv_changed = sv_mod.ensure_running(cfg, shell, config_changed=sb_changed)
    _ok(
        f"sing-box service ({cfg.supervisor.backend})"
        f"{' — started/restarted' if sv_changed else ' — already running'}"
    )

    # 7. Docker bridge CIDRs.
    docker_cidrs: list[str] = []
    if cfg.nftables.auto_detect_docker_bridges:
        docker_cidrs = docker_mod.discover_docker_cidrs(shell)
        if docker_cidrs:
            _ok(f"Docker bridges: {', '.join(docker_cidrs)}")

    # 8. nftables.
    nft_mod.apply_rules(
        cfg.nftables,
        gid,
        cfg.singbox.listen_port,
        shell,
        docker_cidrs,
    )
    _ok(f"nftables {cfg.nftables.table_family} {cfg.nftables.table_name}")

    # 9. Wrapper.
    state = load_state(cfg.state_file)
    if not opts.skip_wrapper:
        _handle_wrapper(cfg, shell, state, opts)
    else:
        console.print("  [dim]Skipped wrapper (--skip-wrapper)[/dim]")

    # 10. Persist state.
    if not opts.dry_run:
        save_state(cfg.state_file, state)

    # 11. Restart notice.
    _print_restart_notice(shell)

    console.print("\n[green]Done.[/green]")


def _handle_wrapper(
    cfg: AppConfig,
    shell: Shell,
    state: object,  # StateFile — avoid circular import at module level
    opts: OnOptions,
) -> None:
    """Discover version and inject wrapper if needed."""
    latest = discover_latest(cfg.antigravity_base_dir, cfg.pin_version)

    if latest is None:
        _warn("No Antigravity version found. Skipping wrapper.")
        return

    match latest.wrapper_status:
        case "unwrapped":
            if not opts.yes:
                proceed = typer.confirm(
                    f"  Inject wrapper into {latest.server_binary}?",
                    default=False,
                )
                if not proceed:
                    console.print("  Skipped wrapper injection.")
                    _print_restart_notice(shell)
                    raise SystemExit(4)

            meta = wrapper_mod.inject_wrapper(latest, cfg.group_name, shell)
            append_change(state, "wrapper", "wrapped", rollback_safe=True, **meta)  # type: ignore[arg-type]
            _ok(f"Wrapper injected: {latest.version[:40]}")

        case "wrapped":
            _ok(f"Wrapper already active: {latest.version[:40]}")

        case _:
            _warn(f"Wrapper status is '{latest.wrapper_status}'. Manual inspection required.")


# -- off ----------------------------------------------------------------------


@dataclass
class OffOptions:
    """Behavioural flags for :func:`run_off`."""

    dry_run: bool = False
    disconnect_warp: bool = False


def run_off(cfg: AppConfig, shell: Shell, opts: OffOptions) -> None:
    """Stop runtime interception (keep wrapper, keep state)."""
    label = "[bold]ag-warp off[/bold]"
    if opts.dry_run:
        label += " [dim](dry-run)[/dim]"
    console.print(f"{label}\n")

    sv_mod.stop_service(cfg, shell)
    _ok("sing-box stopped")

    nft_mod.remove_rules(cfg.nftables, shell)
    _ok("nftables removed")

    if opts.disconnect_warp:
        shell.run(["warp-cli", "--accept-tos", "disconnect"], check=False)
        _ok("WARP disconnected")

    console.print()
    console.print("[dim]Wrapper and state preserved. Use 'rollback' to fully restore.[/dim]")
    _print_restart_notice(shell)


# -- rollback -----------------------------------------------------------------


@dataclass
class RollbackOptions:
    """Behavioural flags for :func:`run_rollback`."""

    dry_run: bool = False
    yes: bool = False


def run_rollback(cfg: AppConfig, shell: Shell, opts: RollbackOptions) -> None:
    """Full rollback: off + safe wrapper restore."""
    label = "[bold]ag-warp rollback[/bold]"
    if opts.dry_run:
        label += " [dim](dry-run)[/dim]"
    console.print(f"{label}\n")

    if not opts.yes:
        proceed = typer.confirm(
            "  This will stop interception and restore the original binary. Continue?",
            default=False,
        )
        if not proceed:
            raise SystemExit(4)

    # 1. Off.
    run_off(cfg, shell, OffOptions(dry_run=opts.dry_run))
    console.print()

    # 2. Safe wrapper restore.
    state = load_state(cfg.state_file)
    latest_wrapper = get_latest_change(state, "wrapper")
    expected_sha: str | None = None
    if latest_wrapper:
        extra = latest_wrapper.model_extra or {}
        expected_sha = extra.get("wrapper_sha256")

    latest = discover_latest(cfg.antigravity_base_dir, cfg.pin_version)
    if latest is None:
        _warn("No Antigravity version found. Skipping wrapper restore.")
    else:
        restored = wrapper_mod.safe_restore(latest, expected_sha, shell)
        if restored:
            _ok(f"Original binary restored: {latest.version[:40]}")
        else:
            console.print()
            console.print("  [yellow]Manual inspection may be needed:[/yellow]")
            console.print(f"    ls -la {latest.bin_dir}/antigravity-server*")

    _print_restart_notice(shell)
    console.print("\n[green]Rollback complete.[/green]")
