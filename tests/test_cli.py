"""Tests for ag_warp.cli helpers."""

from pathlib import Path

from ag_warp.cli import _build_cli_overrides


def test_build_cli_overrides_empty() -> None:
    """No CLI port flags should produce no overrides."""
    assert _build_cli_overrides(
        antigravity_bin_dir=None,
        warp_port=None,
        singbox_port=None,
    ) is None


def test_build_cli_overrides_with_ports() -> None:
    """CLI port flags should map to dotted config keys."""
    overrides = _build_cli_overrides(
        antigravity_bin_dir=None,
        warp_port=40001,
        singbox_port=12346,
    )

    assert overrides == {
        "warp.proxy_port": 40001,
        "singbox.listen_port": 12346,
    }


def test_build_cli_overrides_with_antigravity_bin_dir() -> None:
    """Antigravity bin dir should map to the top-level config field."""
    overrides = _build_cli_overrides(
        antigravity_bin_dir=Path("/home/ubuntu/.antigravity-server/bin"),
        warp_port=None,
        singbox_port=None,
    )

    assert overrides == {
        "antigravity_base_dir": Path("/home/ubuntu/.antigravity-server/bin"),
    }
