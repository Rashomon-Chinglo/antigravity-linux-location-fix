"""WARP proxy management via warp-cli."""

from __future__ import annotations

from dataclasses import dataclass

from ag_warp.config import WarpConfig
from ag_warp.shell import Shell
from ag_warp.ui import console

_WARP_CLI = ["warp-cli", "--accept-tos"]


@dataclass
class WarpStatus:
    connected: bool
    mode: str  # "proxy", "warp", "doh", etc.
    proxy_port: int | None


def get_status(shell: Shell) -> WarpStatus:
    """Query current WARP status."""
    r = shell.run_read([*_WARP_CLI, "status"])
    connected = "Connected" in r.stdout if r.returncode == 0 else False

    mode = "unknown"
    port: int | None = None

    r2 = shell.run_read([*_WARP_CLI, "settings"])
    if r2.returncode == 0:
        mode, port = _parse_settings_output(r2.stdout)

    return WarpStatus(connected=connected, mode=mode, proxy_port=port)


def ensure_proxy_mode(config: WarpConfig, shell: Shell) -> bool:
    """Ensure WARP is in proxy mode on the configured port.

    Returns ``True`` if changes were made.
    """
    status = get_status(shell)
    changed = False

    if status.mode != "proxy":
        console.print("  Setting WARP mode to proxy …")
        shell.run([*_WARP_CLI, "mode", "proxy"])
        changed = True

    if status.proxy_port != config.proxy_port:
        console.print(f"  Setting WARP proxy port to {config.proxy_port} …")
        shell.run([*_WARP_CLI, "proxy", "port", str(config.proxy_port)])
        changed = True

    # Ensure tunnel protocol is MASQUE for reliability.
    shell.run([*_WARP_CLI, "tunnel", "protocol", "set", "MASQUE"])

    if not status.connected:
        console.print("  Connecting WARP …")
        shell.run([*_WARP_CLI, "connect"])
        changed = True

    return changed


def _parse_settings_output(output: str) -> tuple[str, int | None]:
    """Parse the relevant WARP mode information from ``warp-cli settings``."""
    for line in output.splitlines():
        mode_part = _extract_mode_part(line)
        if mode_part is None:
            continue
        return _parse_mode_part(mode_part)
    return ("unknown", None)


def _extract_mode_part(line: str) -> str | None:
    """Extract the mode descriptor from a WARP settings line."""
    if "Mode:" not in line:
        return None
    return line.split("Mode:")[-1].strip()


def _parse_mode_part(mode_part: str) -> tuple[str, int | None]:
    """Parse the WARP mode and optional proxy port from the mode descriptor."""
    return (_detect_mode(mode_part), _extract_port(mode_part))


def _detect_mode(mode_part: str) -> str:
    """Normalize the WARP mode description."""
    if "WarpProxy" in mode_part or "Proxy" in mode_part:
        return "proxy"
    if "Warp" in mode_part:
        return "warp"
    if "DoH" in mode_part:
        return "doh"
    return mode_part.lower()


def _extract_port(mode_part: str) -> int | None:
    """Extract a numeric proxy port from the WARP mode descriptor."""
    if "port" not in mode_part.lower():
        return None
    for token in mode_part.split():
        if token.isdigit():
            return int(token)
    return None
