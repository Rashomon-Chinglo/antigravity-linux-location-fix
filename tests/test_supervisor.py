"""Tests for ag_warp.supervisor."""

import subprocess
from unittest.mock import patch

from ag_warp.config import AppConfig
from ag_warp.shell import Shell
from ag_warp.supervisor import _ensure_pm2, _render_systemd_unit


def test_render_systemd_unit_uses_resolved_binary() -> None:
    cfg = AppConfig()

    unit = _render_systemd_unit(cfg.singbox.config_path, "/usr/bin/sing-box")

    assert "ExecStart=/usr/bin/sing-box run -c /etc/ag-warp/sing-box.json" in unit


def test_pm2_start_uses_resolved_binary() -> None:
    cfg = AppConfig.model_validate({"supervisor": {"backend": "pm2"}})
    shell = Shell()

    with (
        patch.object(shell, "resolve_command", return_value="/usr/bin/sing-box"),
        patch.object(shell, "run_read") as mock_run_read,
        patch.object(shell, "run") as mock_run,
    ):
        mock_run_read.return_value = subprocess.CompletedProcess(
            ["pm2", "pid", cfg.singbox.pm2_app_name],
            0,
            stdout="0\n",
            stderr="",
        )
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        changed = _ensure_pm2(cfg, shell, config_changed=False)

    assert changed is True
    assert mock_run.call_args_list[0].args[0][:3] == ["pm2", "start", "/usr/bin/sing-box"]
