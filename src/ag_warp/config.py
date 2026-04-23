"""Pydantic configuration model with defaults and file overlay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

type SupervisorBackend = Literal["systemd", "pm2"]


class SupervisorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: SupervisorBackend = "systemd"


class WarpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proxy_host: str = "127.0.0.1"
    proxy_port: int = 40000


class SingboxConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listen_host: str = "127.0.0.1"
    listen_port: int = 12345
    service_name: str = "ag-warp-singbox"
    pm2_app_name: str = "sing-box-ag-warp"
    config_path: Path = Path("/etc/ag-warp/sing-box.json")


class NftablesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_family: str = "inet"
    table_name: str = "ag_warp"
    redirect_tcp_ports: list[int] = [80, 443]
    block_udp_ports: list[int] = [443]
    block_public_ipv6: bool = True
    auto_detect_docker_bridges: bool = True
    extra_bypass_cidrs: list[str] = []


class AppConfig(BaseModel):
    """Top-level configuration. All fields have sensible defaults."""

    model_config = ConfigDict(extra="forbid")

    group_name: str = "antigravity-warp"
    antigravity_base_dir: Path = Path("/root/.antigravity-server/bin")
    state_file: Path = Path("/var/lib/ag-warp/state.json")
    pin_version: str | None = None

    supervisor: SupervisorConfig = SupervisorConfig()
    warp: WarpConfig = WarpConfig()
    singbox: SingboxConfig = SingboxConfig()
    nftables: NftablesConfig = NftablesConfig()


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge overlay into base. Lists are replaced, not merged."""
    merged = base.copy()
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from file, merged with built-in defaults.

    If *config_path* is ``None`` or the file does not exist, pure defaults are
    used.  The user file only needs to specify fields they want to override.
    """
    if config_path and config_path.exists():
        with config_path.open() as f:
            user_data = json.load(f)
        # Merge user overrides onto defaults.
        defaults = AppConfig().model_dump(mode="python")
        merged = _deep_merge(defaults, user_data)
        return AppConfig.model_validate(merged)
    return AppConfig()
