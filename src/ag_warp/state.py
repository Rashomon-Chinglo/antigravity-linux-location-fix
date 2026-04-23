"""Append-only state tracking via state.json."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ag_warp.branding import DEFAULT_STATE_FILE, LEGACY_STATE_FILES, preferred_existing_path

SCHEMA_VERSION = 1


class StateChange(BaseModel):
    """A single recorded change."""

    model_config = ConfigDict(extra="allow")

    timestamp: str
    component: str
    action: str
    rollback_safe: bool = True


class StateFile(BaseModel):
    """Persistent state for safe rollback."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    last_apply: str | None = None
    changes: list[StateChange] = Field(default_factory=list)


def load_state(path: Path) -> StateFile:
    """Load state from disk. Returns empty state if file is missing."""
    resolved_path = preferred_existing_path(path, DEFAULT_STATE_FILE, LEGACY_STATE_FILES)
    if resolved_path.exists():
        with resolved_path.open() as f:
            data = json.load(f)
        return StateFile.model_validate(data)
    return StateFile()


def save_state(path: Path, state: StateFile) -> None:
    """Persist state to disk, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(state.model_dump(mode="python"), f, indent=2, default=str)
        f.write("\n")


def append_change(
    state: StateFile,
    component: str,
    action: str,
    *,
    rollback_safe: bool = True,
    **extra: Any,
) -> StateChange:
    """Create a change record and append it to the state."""
    change = StateChange(
        timestamp=datetime.now(UTC).isoformat(),
        component=component,
        action=action,
        rollback_safe=rollback_safe,
        **extra,
    )
    state.changes.append(change)
    state.last_apply = change.timestamp
    return change


def get_latest_change(state: StateFile, component: str) -> StateChange | None:
    """Return the most recent change for *component*, or ``None``."""
    for change in reversed(state.changes):
        if change.component == component:
            return change
    return None
