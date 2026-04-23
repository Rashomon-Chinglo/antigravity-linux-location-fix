"""Tests for ag_warp.verify."""

import subprocess
from unittest.mock import patch

from ag_warp.config import AppConfig
from ag_warp.shell import Shell
from ag_warp.verify import _check_direct_routing, _check_process_group


def test_process_group_check_requires_exact_group_match() -> None:
    shell = Shell()
    output = """\
other-group /usr/bin/language_server --label antigravity-wrap
other-group /usr/bin/extensionHost
"""

    with patch.object(shell, "run_read") as mock_run_read:
        mock_run_read.return_value = subprocess.CompletedProcess(
            ["ps", "-ww", "-eo", "group:64=,args="],
            0,
            stdout=output,
            stderr="",
        )
        result = _check_process_group(AppConfig(), shell)

    assert result.ok is False


def test_process_group_check_passes_for_target_group() -> None:
    shell = Shell()
    output = """\
antigravity-wrap /usr/bin/antigravity-server
antigravity-wrap /usr/bin/language_server --stdio
"""

    with patch.object(shell, "run_read") as mock_run_read:
        mock_run_read.return_value = subprocess.CompletedProcess(
            ["ps", "-ww", "-eo", "group:64=,args="],
            0,
            stdout=output,
            stderr="",
        )
        result = _check_process_group(AppConfig(), shell)

    assert result.ok is True


def test_direct_routing_check_uses_unwrapped_root_group() -> None:
    shell = Shell()

    with patch.object(shell, "run_read") as mock_run_read:
        mock_run_read.return_value = subprocess.CompletedProcess(
            [
                "setpriv",
                "--regid=0",
                "--clear-groups",
                "curl",
                "-sf",
                "-m5",
                "-4",
                "https://www.cloudflare.com/cdn-cgi/trace",
            ],
            0,
            stdout="warp=off\n",
            stderr="",
        )
        result = _check_direct_routing(shell)

    assert result.ok is True
    assert mock_run_read.call_args.args[0][:3] == [
        "setpriv",
        "--regid=0",
        "--clear-groups",
    ]
