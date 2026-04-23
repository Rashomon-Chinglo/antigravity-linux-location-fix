"""Process supervisor abstraction for systemd and PM2."""

from __future__ import annotations

from pathlib import Path

from ag_warp.branding import (
    DEFAULT_PM2_APP_NAME,
    DEFAULT_SERVICE_NAME,
    LEGACY_PM2_APP_NAMES,
    LEGACY_SERVICE_NAMES,
    with_legacy_aliases,
)
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
    if config.supervisor.backend == "systemd":
        return _ensure_systemd(config, shell, config_changed)
    return _ensure_pm2(config, shell, config_changed)


def stop_service(config: AppConfig, shell: Shell) -> None:
    """Stop the sing-box service."""
    if config.supervisor.backend == "systemd":
        _stop_systemd(config, shell)
    else:
        _stop_pm2(config, shell)


def is_running(config: AppConfig, shell: Shell) -> bool:
    """Check whether the sing-box service is currently running."""
    return active_label(config, shell) is not None


def active_label(config: AppConfig, shell: Shell) -> str | None:
    """Return the running service/app label, including legacy names."""
    if config.supervisor.backend == "systemd":
        for svc in _systemd_service_names(config):
            r = shell.run_read(["systemctl", "is-active", "--quiet", svc])
            if r.returncode == 0:
                return svc
        return None

    for app_name in _pm2_app_names(config):
        r = shell.run_read(["pm2", "pid", app_name])
        pid = r.stdout.strip()
        if r.returncode == 0 and pid not in ("", "0"):
            return app_name
    return None


# -- systemd -------------------------------------------------------------------


def _ensure_systemd(config: AppConfig, shell: Shell, config_changed: bool) -> bool:
    svc = config.singbox.service_name
    unit_path = _SYSTEMD_UNIT_DIR / f"{svc}.service"
    singbox_binary = _resolve_singbox_binary(shell)
    _disable_legacy_systemd_units(config, shell)

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
    for svc in _systemd_service_names(config):
        console.print(f"  Stopping and disabling {svc} …")
        shell.run(["systemctl", "disable", "--now", svc], check=False)


# -- PM2 -----------------------------------------------------------------------


def _ensure_pm2(config: AppConfig, shell: Shell, config_changed: bool) -> bool:
    app_name = config.singbox.pm2_app_name
    singbox_binary = _resolve_singbox_binary(shell)
    _delete_legacy_pm2_apps(config, shell)

    r = shell.run_read(["pm2", "pid", app_name])
    pid = r.stdout.strip()
    is_online = r.returncode == 0 and pid not in ("", "0")

    if is_online and not config_changed:
        return False

    if is_online and config_changed:
        console.print(f"  Restarting PM2 app {app_name} …")
        shell.run(["pm2", "restart", app_name])
        return True

    console.print(f"  Starting PM2 app {app_name} …")
    shell.run(
        [
            "pm2",
            "start",
            singbox_binary,
            "--name",
            app_name,
            "--",
            "run",
            "-c",
            str(config.singbox.config_path),
        ]
    )
    shell.run(["pm2", "save"], check=False)
    return True


def _stop_pm2(config: AppConfig, shell: Shell) -> None:
    for app_name in _pm2_app_names(config):
        console.print(f"  Deleting PM2 app {app_name} …")
        shell.run(["pm2", "delete", app_name], check=False)
    shell.run(["pm2", "save"], check=False)


def _resolve_singbox_binary(shell: Shell) -> str:
    """Resolve the sing-box binary path once for service templates and PM2."""
    return shell.resolve_command("sing-box") or "sing-box"


def _render_systemd_unit(config_path: Path, singbox_binary: str) -> str:
    """Render the systemd unit content for sing-box."""
    return _SYSTEMD_TEMPLATE.format(
        config_path=config_path,
        singbox_binary=singbox_binary,
    )


def _systemd_service_names(config: AppConfig) -> tuple[str, ...]:
    return with_legacy_aliases(
        config.singbox.service_name,
        DEFAULT_SERVICE_NAME,
        LEGACY_SERVICE_NAMES,
    )


def _pm2_app_names(config: AppConfig) -> tuple[str, ...]:
    return with_legacy_aliases(
        config.singbox.pm2_app_name,
        DEFAULT_PM2_APP_NAME,
        LEGACY_PM2_APP_NAMES,
    )


def _disable_legacy_systemd_units(config: AppConfig, shell: Shell) -> None:
    if config.singbox.service_name != DEFAULT_SERVICE_NAME:
        return

    for svc in LEGACY_SERVICE_NAMES:
        if svc == config.singbox.service_name:
            continue
        shell.run(["systemctl", "disable", "--now", svc], check=False)


def _delete_legacy_pm2_apps(config: AppConfig, shell: Shell) -> None:
    if config.singbox.pm2_app_name != DEFAULT_PM2_APP_NAME:
        return

    for app_name in LEGACY_PM2_APP_NAMES:
        if app_name == config.singbox.pm2_app_name:
            continue
        shell.run(["pm2", "delete", app_name], check=False)
        shell.run(["pm2", "save"], check=False)
