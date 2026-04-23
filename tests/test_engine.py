"""Tests for ag_warp.engine status output."""

from types import SimpleNamespace
from unittest.mock import patch

from ag_warp.config import AppConfig
from ag_warp.discovery import AntigravityVersion
from ag_warp.engine import (
    OnOptions,
    _handle_wrapper,
    print_antigravity_restart_guidance,
    run_status,
)
from ag_warp.shell import Shell
from ag_warp.state import StateFile, get_latest_change
from ag_warp.ui import console
from ag_warp.wrapper import inject_wrapper


def test_run_status_shows_warp_and_singbox_port_only() -> None:
    cfg = AppConfig()
    shell = Shell()
    warp_status = SimpleNamespace(connected=True, mode="proxy", proxy_port=40000)

    with (
        patch("ag_warp.engine.warp_mod.get_status", return_value=warp_status),
        patch("ag_warp.engine.sv_mod.is_running", return_value=True),
        patch("ag_warp.engine.nft_mod.table_exists", return_value=True),
        patch("ag_warp.engine.nft_mod.active_table_name", return_value="ag_wrap"),
        patch("ag_warp.engine.discover_versions", return_value=[]),
    ):
        with console.capture() as capture:
            run_status(cfg, shell)

    output = capture.get()

    assert "warp: mode=proxy port=40000" in output
    assert "sing-box: port=12345" in output
    assert "systemd" not in output
    assert "cloudflared" not in output


def test_run_status_shows_restart_guidance_when_antigravity_is_running() -> None:
    cfg = AppConfig()
    shell = Shell()
    warp_status = SimpleNamespace(connected=True, mode="proxy", proxy_port=40000)

    with (
        patch("ag_warp.engine.warp_mod.get_status", return_value=warp_status),
        patch("ag_warp.engine.sv_mod.is_running", return_value=True),
        patch("ag_warp.engine.nft_mod.table_exists", return_value=True),
        patch("ag_warp.engine.nft_mod.active_table_name", return_value="ag_wrap"),
        patch("ag_warp.engine.discover_versions", return_value=[]),
        patch("ag_warp.engine.is_antigravity_running", return_value=True),
    ):
        with console.capture() as capture:
            run_status(cfg, shell)

    output = capture.get()

    assert "Antigravity Remote SSH window" in output
    assert "pkill -f antigravity-server" in output


def test_restart_guidance_can_prompt_and_kill_antigravity() -> None:
    shell = Shell()

    with (
        patch("ag_warp.engine.is_antigravity_running", return_value=True),
        patch.object(shell, "has_command", return_value=True),
        patch("ag_warp.engine.typer.confirm", return_value=True),
        patch.object(shell, "run") as mock_run,
    ):
        with console.capture() as capture:
            print_antigravity_restart_guidance(shell, prompt_kill=True)

    output = capture.get()

    assert "CAUTION" in output
    assert "Save any unsaved work first" in output
    mock_run.assert_called_once_with(["pkill", "-f", "antigravity-server"], check=False)


def test_handle_wrapper_updates_group_mismatch(tmp_path) -> None:
    bin_dir = tmp_path / "1.0.0-test" / "bin"
    bin_dir.mkdir(parents=True)
    server = bin_dir / "antigravity-server"
    server.write_bytes(b"\x7fELF_FAKE_BINARY")
    server.chmod(0o700)

    version = AntigravityVersion(
        version="1.0.0-test",
        bin_dir=bin_dir,
        server_binary=server,
        real_binary=bin_dir / "antigravity-server.real",
        mtime=0,
    )
    inject_wrapper(version, "old-group", Shell(dry_run=False))

    cfg = AppConfig.model_validate({"group_name": "new-group"})
    state = StateFile()

    with patch("ag_warp.engine.discover_latest", return_value=version):
        _handle_wrapper(cfg, Shell(dry_run=False), state, OnOptions(yes=True))

    assert 'GROUP_NAME="new-group"' in version.server_binary.read_text()
    latest_change = get_latest_change(state, "wrapper")
    assert latest_change is not None
    assert latest_change.action == "updated"
