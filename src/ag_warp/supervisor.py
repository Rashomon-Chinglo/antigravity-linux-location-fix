"""systemd management for sing-box."""

from __future__ import annotations

from pathlib import Path

from ag_warp.config import AppConfig
from ag_warp.shell import Shell
from ag_warp.ui import console

# -- systemd service template -------------------------------------------------

_SYSTEMD_TEMPLATE = """\
[Unit]
Description=ag-wrap sing-box transparent adapter
After=network-online.target warp-svc.service
Wants=network-online.target

[Service]
Type=simple
ExecStart={singbox_binary} run -c {config_path}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
"""

_SYSTEMD_UNIT_DIR = Path("/etc/systemd/system")


# -- public API ----------------------------------------------------------------


def ensure_running(config: AppConfig, shell: Shell, config_changed: bool = False) -> bool:
    """Make sure the sing-box service is running.

    Returns ``True`` if changes were made.
    """
    return _ensure_systemd(config, shell, config_changed)


def stop_service(config: AppConfig, shell: Shell) -> None:
    """Stop the sing-box service."""
    _stop_systemd(config, shell)


def is_running(config: AppConfig, shell: Shell) -> bool:
    """Check whether the sing-box service is currently running."""
    r = shell.run_read(["systemctl", "is-active", "--quiet", config.singbox.service_name])
    return r.returncode == 0


# -- systemd -------------------------------------------------------------------


def _ensure_systemd(config: AppConfig, shell: Shell, config_changed: bool) -> bool:
    svc = config.singbox.service_name
    unit_path = _SYSTEMD_UNIT_DIR / f"{svc}.service"
    singbox_binary = _resolve_singbox_binary(shell)

    # Generate / update unit file.
    new_unit = _render_systemd_unit(config.singbox.config_path, singbox_binary)
    unit_changed = False

    if unit_path.exists():
        existing = unit_path.read_text()
        if existing != new_unit:
            unit_changed = True
    else:
        unit_changed = True

    if unit_changed:
        console.print(f"  Installing systemd unit {unit_path.name} …")
        shell.run(["tee", str(unit_path)], input_text=new_unit)
        shell.run(["systemctl", "daemon-reload"])

    # Enable + start.
    r = shell.run_read(["systemctl", "is-enabled", "--quiet", svc])
    if r.returncode != 0:
        shell.run(["systemctl", "enable", svc])

    if config_changed or unit_changed:
        console.print(f"  Restarting {svc} …")
        shell.run(["systemctl", "restart", svc])
        return True

    r = shell.run_read(["systemctl", "is-active", "--quiet", svc])
    if r.returncode != 0:
        console.print(f"  Starting {svc} …")
        shell.run(["systemctl", "start", svc])
        return True

    return False


def _stop_systemd(config: AppConfig, shell: Shell) -> None:
    svc = config.singbox.service_name
    console.print(f"  Stopping and disabling {svc} …")
    shell.run(["systemctl", "disable", "--now", svc], check=False)


def _resolve_singbox_binary(shell: Shell) -> str:
    """Resolve the sing-box binary path once for service templates and PM2."""
    return shell.resolve_command("sing-box") or "sing-box"


def _render_systemd_unit(config_path: Path, singbox_binary: str) -> str:
    """Render the systemd unit content for sing-box."""
    return _SYSTEMD_TEMPLATE.format(
        config_path=config_path,
        singbox_binary=singbox_binary,
    )
