"""Tests for ag_warp.warp helpers."""

from ag_warp.warp import _parse_settings_output


def test_parse_settings_output_proxy_mode() -> None:
    """WarpProxy settings should parse mode and port."""
    output = "(user set)      Mode: WarpProxy on port 40000\n"

    assert _parse_settings_output(output) == ("proxy", 40000)


def test_parse_settings_output_non_proxy_mode() -> None:
    """Non-proxy WARP modes should parse without a port."""
    output = "Mode: Warp\n"

    assert _parse_settings_output(output) == ("warp", None)


def test_parse_settings_output_without_mode_line() -> None:
    """Missing mode lines should fall back to unknown."""
    output = "Tunnel protocol: MASQUE\n"

    assert _parse_settings_output(output) == ("unknown", None)
