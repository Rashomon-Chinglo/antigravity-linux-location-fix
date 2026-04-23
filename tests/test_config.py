"""Tests for ag_warp.config."""

from pathlib import Path

import pytest

from ag_warp.config import AppConfig, load_config


def test_defaults() -> None:
    """Pure defaults should produce a valid config."""
    cfg = AppConfig()
    assert cfg.group_name == "antigravity-warp"
    assert cfg.warp.proxy_port == 40000
    assert cfg.singbox.listen_port == 12345
    assert cfg.nftables.redirect_tcp_ports == [80, 443]
    assert cfg.nftables.block_udp_ports == [443]
    assert cfg.nftables.block_public_ipv6 is True


def test_load_missing_file() -> None:
    """Loading a non-existent file should return defaults."""
    cfg = load_config(Path("/does/not/exist.json"))
    assert cfg == AppConfig()


def test_load_partial_override(tmp_path: Path) -> None:
    """Partial config should merge onto defaults."""
    config_file = tmp_path / "config.json"
    config_file.write_text('{"warp": {"proxy_port": 50000}}')

    cfg = load_config(config_file)
    assert cfg.warp.proxy_port == 50000
    # Unspecified fields keep defaults.
    assert cfg.warp.proxy_host == "127.0.0.1"
    assert cfg.singbox.listen_port == 12345


def test_list_fields_are_replaced(tmp_path: Path) -> None:
    """List fields should be replaced, not merged."""
    config_file = tmp_path / "config.json"
    config_file.write_text('{"nftables": {"redirect_tcp_ports": [80, 443, 8443]}}')

    cfg = load_config(config_file)
    assert cfg.nftables.redirect_tcp_ports == [80, 443, 8443]


def test_extra_fields_rejected(tmp_path: Path) -> None:
    """Unknown fields should raise an error."""
    config_file = tmp_path / "config.json"
    config_file.write_text('{"unknown_field": true}')

    with pytest.raises(Exception):
        load_config(config_file)
