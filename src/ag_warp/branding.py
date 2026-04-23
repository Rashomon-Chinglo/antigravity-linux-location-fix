"""Project naming constants."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "ag-wrap"
BINARY_NAME = APP_NAME

DEFAULT_GROUP_NAME = "antigravity-wrap"

DEFAULT_SERVICE_NAME = "ag-wrap-singbox"

DEFAULT_CONFIG_PATH = Path("/etc/ag-wrap/sing-box.json")

DEFAULT_STATE_FILE = Path("/var/lib/ag-wrap/state.json")

DEFAULT_NFT_TABLE_NAME = "ag_wrap"

DEFAULT_LOCK_PATH = Path("/var/run/ag-wrap.lock")

WRAPPER_MARKERS = (
    "# ag-wrap wrapper",
    "# antigravity-wrap wrapper",
)

RICH_INCLUDE_PACKAGE = "rich._unicode_data"


def command_label(subcommand: str | None = None) -> str:
    """Return the displayed CLI command name."""
    if not subcommand:
        return APP_NAME
    return f"{APP_NAME} {subcommand}"
