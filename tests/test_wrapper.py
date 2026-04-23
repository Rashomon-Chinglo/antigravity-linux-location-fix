"""Tests for ag_warp.wrapper."""

import stat
from pathlib import Path

from ag_warp.discovery import AntigravityVersion
from ag_warp.shell import Shell
from ag_warp.wrapper import inject_wrapper, read_wrapper_group_name, update_wrapper_group


def _make_fake_version(tmp_path: Path) -> AntigravityVersion:
    """Create a fake unwrapped Antigravity version."""
    bin_dir = tmp_path / "1.0.0-test" / "bin"
    bin_dir.mkdir(parents=True)
    server = bin_dir / "antigravity-server"
    server.write_bytes(b"\x7fELF_FAKE_BINARY")
    server.chmod(stat.S_IRWXU)
    real = bin_dir / "antigravity-server.real"
    return AntigravityVersion(
        version="1.0.0-test",
        bin_dir=bin_dir,
        server_binary=server,
        real_binary=real,
        mtime=0,
    )


def test_inject_wrapper(tmp_path: Path) -> None:
    version = _make_fake_version(tmp_path)
    shell = Shell(dry_run=False)

    meta = inject_wrapper(version, "antigravity-wrap", shell)

    # Wrapper should exist and contain marker.
    assert version.server_binary.exists()
    content = version.server_binary.read_text()
    assert "# ag-wrap wrapper" in content
    assert "antigravity-wrap" in content

    # .real should exist.
    assert version.real_binary.exists()

    # Metadata should be populated.
    assert meta["version"] == "1.0.0-test"
    assert meta["original_sha256"]
    assert meta["wrapper_sha256"]


def test_wrapper_uses_relative_path(tmp_path: Path) -> None:
    version = _make_fake_version(tmp_path)
    shell = Shell(dry_run=False)

    inject_wrapper(version, "antigravity-wrap", shell)

    content = version.server_binary.read_text()
    # Should use $(dirname "$0") not absolute path.
    assert '$(dirname "$0")/antigravity-server.real' in content
    # Should NOT contain an absolute path to .real.
    assert str(tmp_path) not in content


def test_read_wrapper_group_name(tmp_path: Path) -> None:
    version = _make_fake_version(tmp_path)
    shell = Shell(dry_run=False)

    inject_wrapper(version, "antigravity-wrap", shell)

    assert read_wrapper_group_name(version) == "antigravity-wrap"


def test_update_wrapper_group_rewrites_existing_wrapper(tmp_path: Path) -> None:
    version = _make_fake_version(tmp_path)
    shell = Shell(dry_run=False)

    inject_wrapper(version, "old-group", shell)
    real_before = version.real_binary.read_bytes()

    meta = update_wrapper_group(version, "new-group", shell)

    assert 'GROUP_NAME="new-group"' in version.server_binary.read_text()
    assert version.real_binary.read_bytes() == real_before
    assert meta["wrapper_sha256"]
