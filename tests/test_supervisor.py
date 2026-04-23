"""Tests for ag_warp.supervisor."""

from ag_warp.config import AppConfig
from ag_warp.supervisor import _render_systemd_unit


def test_render_systemd_unit_uses_resolved_binary() -> None:
    cfg = AppConfig()

    unit = _render_systemd_unit(cfg.singbox.config_path, "/usr/bin/sing-box")

    assert "ExecStart=/usr/bin/sing-box run -c /etc/ag-wrap/sing-box.json" in unit
