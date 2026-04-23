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
    port: int | None = None

    r2 = shell.run_read(["warp-cli", "--accept-tos", "settings"])
    if r2.returncode == 0:
        for line in r2.stdout.splitlines():
            # Format: "(user set)      Mode: WarpProxy on port 40000"
            if "Mode:" in line:
                mode_part = line.split("Mode:")[-1].strip()
                if "WarpProxy" in mode_part or "Proxy" in mode_part:
                    mode = "proxy"
                elif "Warp" in mode_part:
                    mode = "warp"
                elif "DoH" in mode_part:
                    mode = "doh"
                else:
                    mode = mode_part.lower()

                # Extract port number if present.
                if "port" in mode_part.lower():
                    for token in mode_part.split():
                        if token.isdigit():
                            port = int(token)
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
