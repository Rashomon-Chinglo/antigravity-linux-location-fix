"""System-level operations: GID management, dependency checking, port probing."""

from __future__ import annotations

from ag_warp.config import AppConfig
from ag_warp.shell import Shell
from ag_warp.ui import console

# -- group management ---------------------------------------------------------


def resolve_gid(group_name: str, shell: Shell) -> int | None:
    """Look up the numeric GID for *group_name*. Returns ``None`` if absent."""
    r = shell.run_read(["getent", "group", group_name])
    if r.returncode != 0:
        return None
    parts = r.stdout.strip().split(":")
    return int(parts[2]) if len(parts) >= 3 else None


def ensure_group(group_name: str, shell: Shell) -> int:
    """Create *group_name* if missing. Returns numeric GID.

    Raises :class:`SystemExit` if creation fails.
    """
    gid = resolve_gid(group_name, shell)
    if gid is not None:
        return gid
    console.print(f"  Creating group {group_name} …")
    shell.run(["groupadd", "--system", group_name])
    gid = resolve_gid(group_name, shell)
    if gid is None:
        console.print(f"[red]✗ Failed to create group {group_name}[/red]")
        raise SystemExit(1)
    return gid


# -- dependency checking (doctor) --------------------------------------------

# Required commands that must exist.
_BASE_REQUIRED = [
    "warp-cli",
    "sing-box",
    "nft",
    "setpriv",
    "curl",
    "ss",
    "ps",
    "getent",
]

# Optional commands (informational only).
_OPTIONAL = ["docker", "cloudflared"]


def doctor_check(cfg: AppConfig, shell: Shell, *, verbose: bool = False) -> bool:
    """Return ``True`` if all required system commands are present."""
    required = _required_commands(cfg)

    all_ok = True
    for cmd in required:
        found = shell.has_command(cmd)
        if verbose:
            icon = "[green]✓[/green]" if found else "[red]✗[/red]"
            suffix = "" if found else " [red](REQUIRED)[/red]"
            console.print(f"  {icon} {cmd}{suffix}")
        if not found:
            all_ok = False

    if verbose:
        for cmd in _OPTIONAL:
            found = shell.has_command(cmd)
            icon = "[green]✓[/green]" if found else "[dim]○[/dim]"
            suffix = "" if found else " (optional)"
            console.print(f"  {icon} {cmd}{suffix}")

    return all_ok


def _required_commands(cfg: AppConfig) -> list[str]:
    """Return the required command list for the configured supervisor backend."""
    required = list(_BASE_REQUIRED)
    required.append("systemctl" if cfg.supervisor.backend == "systemd" else "pm2")
    return required


# -- port probing -------------------------------------------------------------


def is_port_in_use(port: int, shell: Shell) -> str | None:
    """Check whether *port* is already bound.

    Returns the process description string if in use, ``None`` if free.
    """
    r = shell.run_read(["ss", "-ltnp", f"sport = :{port}"])
    if r.returncode != 0:
        return None
    # Skip the header line.
    lines = [line for line in r.stdout.strip().splitlines()[1:] if line.strip()]
    if not lines:
        return None
    # Return the first match's process info.
    return lines[0].strip()


def check_port_availability(
    warp_port: int,
    singbox_port: int,
    shell: Shell,
) -> list[str]:
    """Validate that required ports are available.

    Returns a list of error messages. Empty list means all ports are free
    (or already held by our own services).
    """
    errors: list[str] = []
    for label, port in [("WARP proxy", warp_port), ("sing-box", singbox_port)]:
        info = is_port_in_use(port, shell)
        if info is None:
            continue
        # If it's our own service, that's fine.
        if "sing-box" in info or "warp" in info.lower():
            continue
        errors.append(f"Port {port} ({label}) already in use: {info[:80]}")
    return errors


# -- process probing ----------------------------------------------------------


def is_antigravity_running(shell: Shell) -> bool:
    """Return ``True`` if any Antigravity server processes are running."""
    r = shell.run_read(["pgrep", "-f", "antigravity-server"])
    return r.returncode == 0
