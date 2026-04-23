"""Tests for ag_warp.state legacy fallback behaviour."""

import json

from ag_warp.branding import DEFAULT_STATE_FILE, LEGACY_STATE_FILES
from ag_warp.state import load_state


def test_load_state_prefers_existing_legacy_file(tmp_path, monkeypatch) -> None:
    legacy_path = tmp_path / "legacy-state.json"
    legacy_path.write_text(json.dumps({"schema_version": 1, "changes": [], "last_apply": None}))

    monkeypatch.setattr("ag_warp.state.DEFAULT_STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr("ag_warp.state.LEGACY_STATE_FILES", (legacy_path,))

    state = load_state(tmp_path / "state.json")

    assert state.schema_version == 1


def test_branding_state_defaults_are_distinct() -> None:
    assert DEFAULT_STATE_FILE not in LEGACY_STATE_FILES
