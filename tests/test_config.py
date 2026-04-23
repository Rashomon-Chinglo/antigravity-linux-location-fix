"""Tests for ag_warp.config."""

from pathlib import Path

import pytest

from ag_warp.config import AppConfig, load_config


def test_defaults() -> None:
    """Pure defaults should produce a valid config."""
    cfg = AppConfig()
    assert cfg.group_name == "antigravity-wrap"
    assert cfg.warp.proxy_port == 40000
    assert cfg.singbox.listen_port == 12345
    assert cfg.nftables.redirect_tcp_ports == [80, 443]
    assert cfg.nftables.block_udp_ports == [443]
    assert cfg.nftables.block_public_ipv6 is True


def test_load_defaults_without_file() -> None:
    """Omitting a config file should return defaults."""
    cfg = load_config()
    assert cfg == AppConfig()


def test_missing_explicit_config_file_raises() -> None:
    """Passing a missing config path should fail fast."""
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config(Path("/does/not/exist.json"))


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


# -- port conflict tests -------------------------------------------------------


def test_port_conflict_raises() -> None:
    """Same port for WARP and sing-box should fail validation."""
    with pytest.raises(ValueError, match="Port conflict"):
        AppConfig.model_validate(
            {
                "warp": {"proxy_port": 12345},
                "singbox": {"listen_port": 12345},
            }
        )


def test_port_conflict_via_config_file(tmp_path: Path) -> None:
    """Port conflict from config file should raise."""
    config_file = tmp_path / "config.json"
    config_file.write_text('{"warp": {"proxy_port": 9999}, "singbox": {"listen_port": 9999}}')
    with pytest.raises(Exception, match="Port conflict"):
        load_config(config_file)


# -- CLI override tests --------------------------------------------------------


def test_cli_overrides() -> None:
    """CLI flags should override defaults."""
    cfg = load_config(
        cli_overrides={"warp.proxy_port": 50000, "singbox.listen_port": 54321},
    )
    assert cfg.warp.proxy_port == 50000
    assert cfg.singbox.listen_port == 54321


def test_cli_overrides_beat_file(tmp_path: Path) -> None:
    """CLI flags should override config file values."""
    config_file = tmp_path / "config.json"
    config_file.write_text('{"warp": {"proxy_port": 30000}}')

    cfg = load_config(
        config_file,
        cli_overrides={"warp.proxy_port": 60000},
    )
    assert cfg.warp.proxy_port == 60000


def test_cli_override_port_conflict() -> None:
    """CLI overrides causing a port conflict should fail."""
    with pytest.raises(Exception, match="Port conflict"):
        load_config(
            cli_overrides={
                "warp.proxy_port": 12345,
                "singbox.listen_port": 12345,
            },
        )


def test_invalid_port_range_rejected() -> None:
    """Ports must stay within the valid TCP/UDP range."""
    with pytest.raises(Exception, match="less than or equal to 65535"):
        AppConfig.model_validate({"warp": {"proxy_port": 70000}})


def test_redirect_ports_must_not_be_empty() -> None:
    """The redirect chain needs at least one TCP port to intercept."""
    with pytest.raises(Exception, match="must not be empty"):
        AppConfig.model_validate({"nftables": {"redirect_tcp_ports": []}})


def test_invalid_extra_bypass_cidr_rejected() -> None:
    """Invalid bypass CIDRs should fail during config validation."""
    with pytest.raises(Exception):
        AppConfig.model_validate({"nftables": {"extra_bypass_cidrs": ["not-a-cidr"]}})


def test_default_antigravity_base_dir_uses_current_home(monkeypatch, tmp_path: Path) -> None:
    """Without sudo, the current user's home should determine the default path."""
    monkeypatch.setattr("ag_warp.config._sudo_user_home", lambda: None)
    monkeypatch.setattr("ag_warp.config.Path.home", lambda: tmp_path)

    cfg = AppConfig()

    assert cfg.antigravity_base_dir == tmp_path / ".antigravity-server" / "bin"


def test_default_antigravity_base_dir_prefers_sudo_user_home(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """When invoked via sudo, prefer the original user's Antigravity path."""
    sudo_home = tmp_path / "ubuntu"
    monkeypatch.setattr("ag_warp.config._sudo_user_home", lambda: sudo_home)
    monkeypatch.setattr("ag_warp.config.Path.home", lambda: tmp_path / "root")

    cfg = AppConfig()

    assert cfg.antigravity_base_dir == sudo_home / ".antigravity-server" / "bin"
