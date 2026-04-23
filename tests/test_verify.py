"""Tests for ag_warp.verify."""

import subprocess
from unittest.mock import patch

from ag_warp.config import AppConfig
from ag_warp.shell import Shell
from ag_warp.verify import _check_process_group


def test_process_group_check_requires_exact_group_match() -> None:
    shell = Shell()
    output = """\
other-group /usr/bin/language_server --label antigravity-warp
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
antigravity-warp /usr/bin/antigravity-server
antigravity-warp /usr/bin/language_server --stdio
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
