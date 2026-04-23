"""Tests for ag_warp.shell."""

import subprocess
from unittest.mock import patch

import pytest

from ag_warp.shell import Shell
from ag_warp.ui import console


def test_run_prints_stderr_before_reraising() -> None:
    shell = Shell()
    error = subprocess.CalledProcessError(
        1,
        ["nft", "-f", "-"],
        stderr="nft: syntax error",
    )

    with patch("ag_warp.shell.subprocess.run", side_effect=error):
        with console.capture() as capture:
            with pytest.raises(subprocess.CalledProcessError):
                shell.run(["nft", "-f", "-"])

    output = capture.get()
    assert "Command failed" in output
    assert "nft: syntax error" in output
