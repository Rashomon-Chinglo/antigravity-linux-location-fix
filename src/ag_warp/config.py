"""Pydantic configuration model with defaults, file overlay, and CLI overrides."""

from __future__ import annotations

import json
import os
import pwd
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, IPvAnyNetwork, model_validator

from ag_warp.branding import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_GROUP_NAME,
    DEFAULT_NFT_TABLE_NAME,
    DEFAULT_SERVICE_NAME,
    DEFAULT_STATE_FILE,
)

type Port = Annotated[int, Field(ge=1, le=65535)]


def _default_antigravity_base_dir() -> Path:
    """Resolve the most likely Antigravity installation path for this session."""
    sudo_home = _sudo_user_home()
    if sudo_home is not None:
        return sudo_home / ".antigravity-server" / "bin"
    return Path.home() / ".antigravity-server" / "bin"


def _sudo_user_home() -> Path | None:
    """Return the invoking sudo user's home directory, if available."""
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user or sudo_user == "root":
        return None
    try:
        return Path(pwd.getpwnam(sudo_user).pw_dir)
    except KeyError:
        return None


class WarpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proxy_host: str = "127.0.0.1"
    proxy_port: Port = 40000


class SingboxConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listen_host: str = "127.0.0.1"
    listen_port: Port = 12345
    service_name: str = DEFAULT_SERVICE_NAME
    config_path: Path = DEFAULT_CONFIG_PATH


class NftablesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_family: str = "inet"
    table_name: str = DEFAULT_NFT_TABLE_NAME
    redirect_tcp_ports: list[Port] = Field(default_factory=lambda: [80, 443])
    block_udp_ports: list[Port] = Field(default_factory=lambda: [443])
    block_public_ipv6: bool = True
    auto_detect_docker_bridges: bool = True
    extra_bypass_cidrs: list[IPvAnyNetwork] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_redirect_ports(self) -> NftablesConfig:
        """Ensure nft redirect rules always have at least one TCP port."""
        if not self.redirect_tcp_ports:
            raise ValueError("nftables.redirect_tcp_ports must not be empty.")
        return self


class AppConfig(BaseModel):
    """Top-level configuration. All fields have sensible defaults."""

    model_config = ConfigDict(extra="forbid")

    group_name: str = DEFAULT_GROUP_NAME
    antigravity_base_dir: Path = Field(default_factory=_default_antigravity_base_dir)
    state_file: Path = DEFAULT_STATE_FILE
    pin_version: str | None = None

    warp: WarpConfig = Field(default_factory=WarpConfig)
    singbox: SingboxConfig = Field(default_factory=SingboxConfig)
    nftables: NftablesConfig = Field(default_factory=NftablesConfig)

    @model_validator(mode="after")
    def _validate_ports(self) -> AppConfig:
        """Ensure WARP proxy port and sing-box listen port don't collide."""
        if self.warp.proxy_port == self.singbox.listen_port:
            msg = (
                f"Port conflict: warp.proxy_port ({self.warp.proxy_port}) "
                f"and singbox.listen_port ({self.singbox.listen_port}) "
                f"must be different."
            )
            raise ValueError(msg)
        return self


# -- config loading & merging ------------------------------------------------


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base. Lists are replaced, not merged."""
    merged = base.copy()
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(
    config_path: Path | None = None,
    *,
    cli_overrides: dict[str, Any] | None = None,
) -> AppConfig:
    """Load configuration with three-layer precedence.

    Priority (highest → lowest):
        1. CLI flags (``cli_overrides``)
        2. Config file (``config_path``)
        3. Built-in defaults

    ``cli_overrides`` uses dotted-path keys::

        {"warp.proxy_port": 50000, "singbox.listen_port": 54321}
    """
    defaults = AppConfig().model_dump(mode="python")
    data = dict(defaults)

    # Layer 2: config file.
    if config_path is not None:
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        with config_path.open() as f:
            user_data = json.load(f)
        data = _deep_merge(data, user_data)

    # Layer 1: CLI overrides.
    if cli_overrides:
        data = _deep_merge(data, _expand_dotted(cli_overrides))

    return AppConfig.model_validate(data)


def _expand_dotted(flat: dict[str, Any]) -> dict[str, Any]:
    """Expand dotted keys into nested dicts.

    Example::

        {"warp.proxy_port": 50000}  →  {"warp": {"proxy_port": 50000}}
    """
    result: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        current = result
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return result
