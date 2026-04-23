"""Dynamic discovery of Antigravity server binary versions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

type WrapperStatus = Literal["wrapped", "unwrapped", "stale", "unknown"]

# Marker line embedded in the generated wrapper script.
WRAPPER_MARKER = "# ag-warp wrapper"


@dataclass
class AntigravityVersion:
    """Discovered Antigravity installation."""

    version: str
    bin_dir: Path
    server_binary: Path
    real_binary: Path
    mtime: float

    @property
    def wrapper_status(self) -> WrapperStatus:
        """Determine the current wrapper state of this version."""
        server = self.server_binary
        real = self.real_binary

        if not server.exists():
            return "unknown"

        has_real = real.exists()
        is_wrapper = _is_ag_warp_wrapper(server)

        if is_wrapper and has_real:
            return "wrapped"
        if not is_wrapper and not has_real:
            return "unwrapped"
        if is_wrapper and not has_real:
            # Wrapper exists but .real is missing — dangerous, don't touch.
            return "unknown"
        # .real exists but server is not our wrapper — someone else modified it.
        return "stale" if has_real else "unknown"


def discover_versions(base_dir: Path) -> list[AntigravityVersion]:
    """Scan *base_dir* for all Antigravity version directories.

    Returns versions sorted by mtime descending (newest first).
    """
    if not base_dir.is_dir():
        return []

    versions: list[AntigravityVersion] = []
    for version_dir in base_dir.iterdir():
        if not version_dir.is_dir():
            continue
        bin_dir = version_dir / "bin"
        server = bin_dir / "antigravity-server"
        real = bin_dir / "antigravity-server.real"

        # Must have at least one of the two files.
        if not server.exists() and not real.exists():
            continue

        versions.append(
            AntigravityVersion(
                version=version_dir.name,
                bin_dir=bin_dir,
                server_binary=server,
                real_binary=real,
                mtime=version_dir.stat().st_mtime,
            )
        )

    versions.sort(key=lambda v: v.mtime, reverse=True)
    return versions


def discover_latest(
    base_dir: Path,
    pin_version: str | None = None,
) -> AntigravityVersion | None:
    """Find the latest (or pinned) Antigravity version.

    Returns ``None`` if no version is found.
    """
    versions = discover_versions(base_dir)
    if not versions:
        return None

    if pin_version:
        for v in versions:
            if v.version == pin_version:
                return v
        return None

    return versions[0]


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_ag_warp_wrapper(path: Path) -> bool:
    """Check whether *path* contains the ag-warp wrapper marker."""
    try:
        content = path.read_text(errors="replace")
        return WRAPPER_MARKER in content
    except OSError:
        return False
