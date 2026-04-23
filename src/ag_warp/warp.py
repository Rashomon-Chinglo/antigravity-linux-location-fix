"""WARP proxy management via warp-cli."""

from __future__ import annotations

from dataclasses import dataclass

from ag_warp.config import WarpConfig
from ag_warp.shell import Shell, console


@dataclass
class WarpStatus:
    connected: bool
    mode: str  # "proxy", "warp", "doh", etc.
    proxy_port: int | None


def get_status(shell: Shell) -> WarpStatus:
    """Query current WARP status."""
    r = shell.run_read(["warp-cli", "--accept-tos", "status"])
    connected = "Connected" in r.stdout if r.returncode == 0 else False

    mode = "unknown"
    r2 = shell.run_read(["warp-cli", "--accept-tos", "settings"])
    if r2.returncode == 0:
        for line in r2.stdout.splitlines():
            if "Mode" in line:
                mode = line.split()[-1].lower() if line.split() else "unknown"
                break

    port: int | None = None
    if r2.returncode == 0:
        for line in r2.stdout.splitlines():
            if "proxy port" in line.lower() or "Proxy port" in line:
                parts = line.split()
                for p in parts:
                    if p.isdigit():
                        port = int(p)
                        break

    return WarpStatus(connected=connected, mode=mode, proxy_port=port)


def ensure_proxy_mode(config: WarpConfig, shell: Shell) -> bool:
    """Ensure WARP is in proxy mode on the configured port.

    Returns ``True`` if changes were made.
    """
    status = get_status(shell)
    changed = False

    if status.mode != "proxy":
        console.print("  Setting WARP mode to proxy …")
        shell.run(["warp-cli", "--accept-tos", "mode", "proxy"])
        changed = True

    if status.proxy_port != config.proxy_port:
        console.print(f"  Setting WARP proxy port to {config.proxy_port} …")
        shell.run(["warp-cli", "--accept-tos", "proxy", "port", str(config.proxy_port)])
        changed = True

    # Ensure tunnel protocol is MASQUE for reliability.
    shell.run(["warp-cli", "--accept-tos", "tunnel", "protocol", "set", "MASQUE"])

    if not status.connected:
        console.print("  Connecting WARP …")
        shell.run(["warp-cli", "--accept-tos", "connect"])
        changed = True

    return changed
