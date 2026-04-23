"""sing-box configuration generation."""

from __future__ import annotations

import json
from pathlib import Path

from ag_warp.config import SingboxConfig, WarpConfig


def generate_config(singbox: SingboxConfig, warp: WarpConfig) -> str:
    """Generate a sing-box JSON configuration string."""
    cfg = {
        "log": {
            "level": "info",
            "timestamp": True,
        },
        "inbounds": [
            {
                "type": "redirect",
                "tag": "ag-redirect",
                "listen": singbox.listen_host,
                "listen_port": singbox.listen_port,
                "sniff": True,
                "sniff_override_destination": False,
            }
        ],
        "outbounds": [
            {
                "type": "http",
                "tag": "warp-proxy",
                "server": warp.proxy_host,
                "server_port": warp.proxy_port,
            },
            {
                "type": "direct",
                "tag": "direct",
            },
        ],
        "route": {
            "final": "warp-proxy",
        },
    }
    return json.dumps(cfg, indent=2) + "\n"


def ensure_config(singbox: SingboxConfig, warp: WarpConfig, dry_run: bool = False) -> bool:
    """Write sing-box config if content has changed.

    Returns ``True`` if the file was written (i.e. content changed).
    """
    new_content = generate_config(singbox, warp)
    config_path = Path(singbox.config_path)

    if config_path.exists():
        existing = config_path.read_text()
        if existing == new_content:
            return False

    if dry_run:
        return True

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(new_content)
    return True
