"""Tests for ag_warp.system."""

import subprocess
from unittest.mock import patch

from ag_warp.config import AppConfig
from ag_warp.shell import Shell
from ag_warp.system import doctor_check


def test_doctor_check_passes_when_warp_service_is_active() -> None:
    shell = Shell()

    with (
        patch.object(shell, "has_command", return_value=True),
        patch.object(
            shell,
            "run_read",
            return_value=subprocess.CompletedProcess(
                ["systemctl", "is-active", "--quiet", "warp-svc"],
                0,
                stdout="",
                stderr="",
            ),
        ),
    ):
        assert doctor_check(AppConfig(), shell) is True


def test_doctor_check_fails_when_warp_service_is_inactive() -> None:
    shell = Shell()

    with (
        patch.object(shell, "has_command", return_value=True),
        patch.object(
            shell,
            "run_read",
            return_value=subprocess.CompletedProcess(
                ["systemctl", "is-active", "--quiet", "warp-svc"],
                3,
                stdout="inactive\n",
                stderr="",
            ),
        ),
    ):
        assert doctor_check(AppConfig(), shell) is False
