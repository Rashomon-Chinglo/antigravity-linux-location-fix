"""Tests for ag_warp.discovery."""

import stat
from pathlib import Path

from ag_warp.discovery import (
    discover_latest,
    discover_versions,
)


def _make_version(
    base: Path,
    name: str,
    *,
    wrapper: bool = False,
    real: bool = False,
) -> Path:
    """Create a fake Antigravity version directory."""
    bin_dir = base / name / "bin"
    bin_dir.mkdir(parents=True)

    server = bin_dir / "antigravity-server"
    if wrapper:
        server.write_text("#!/usr/bin/env sh\n# ag-warp wrapper\nexec true\n")
    else:
        server.write_bytes(b"\x7fELF_FAKE_BINARY")
    server.chmod(stat.S_IRWXU)

    if real:
        real_bin = bin_dir / "antigravity-server.real"
        real_bin.write_bytes(b"\x7fELF_REAL_BINARY")
        real_bin.chmod(stat.S_IRWXU)

    return bin_dir


def test_discover_empty(tmp_path: Path) -> None:
    versions = discover_versions(tmp_path)
    assert versions == []


def test_discover_single_unwrapped(tmp_path: Path) -> None:
    _make_version(tmp_path, "1.0.0-abc")

    versions = discover_versions(tmp_path)
    assert len(versions) == 1
    assert versions[0].version == "1.0.0-abc"
    assert versions[0].wrapper_status == "unwrapped"


def test_discover_wrapped(tmp_path: Path) -> None:
    _make_version(tmp_path, "1.0.0-abc", wrapper=True, real=True)

    versions = discover_versions(tmp_path)
    assert len(versions) == 1
    assert versions[0].wrapper_status == "wrapped"


def test_discover_latest_by_mtime(tmp_path: Path) -> None:
    import time

    _make_version(tmp_path, "1.0.0-old")
    time.sleep(0.05)
    _make_version(tmp_path, "2.0.0-new")

    latest = discover_latest(tmp_path)
    assert latest is not None
    assert latest.version == "2.0.0-new"


def test_discover_pinned(tmp_path: Path) -> None:
    _make_version(tmp_path, "1.0.0-old")
    _make_version(tmp_path, "2.0.0-new")

    pinned = discover_latest(tmp_path, pin_version="1.0.0-old")
    assert pinned is not None
    assert pinned.version == "1.0.0-old"
