"""Project naming and legacy compatibility constants."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "ag-wrap"
LEGACY_APP_NAME = "ag-warp"
BINARY_NAME = APP_NAME
LEGACY_BINARY_NAMES = (LEGACY_APP_NAME,)

# Keep the wrapper group stable for old deployments. Renaming the Linux group
# would require rewriting already-injected wrappers on user machines.
DEFAULT_GROUP_NAME = "antigravity-warp"

DEFAULT_SERVICE_NAME = "ag-wrap-singbox"
LEGACY_SERVICE_NAMES = ("ag-warp-singbox",)

DEFAULT_PM2_APP_NAME = "sing-box-ag-wrap"
LEGACY_PM2_APP_NAMES = ("sing-box-ag-warp",)

DEFAULT_CONFIG_PATH = Path("/etc/ag-wrap/sing-box.json")
LEGACY_CONFIG_PATHS = (Path("/etc/ag-warp/sing-box.json"),)

DEFAULT_STATE_FILE = Path("/var/lib/ag-wrap/state.json")
LEGACY_STATE_FILES = (Path("/var/lib/ag-warp/state.json"),)

DEFAULT_NFT_TABLE_NAME = "ag_wrap"
LEGACY_NFT_TABLE_NAMES = ("ag_warp",)

DEFAULT_LOCK_PATH = Path("/var/run/ag-wrap.lock")

WRAPPER_MARKERS = (
    "# ag-wrap wrapper",
    "# ag-warp wrapper",
    "# antigravity-wrap wrapper",
    "# antigravity-warp wrapper",
)

RICH_INCLUDE_PACKAGE = "rich._unicode_data"


def command_label(subcommand: str | None = None) -> str:
    """Return the displayed CLI command name."""
    if not subcommand:
        return APP_NAME
    return f"{APP_NAME} {subcommand}"


def with_legacy_aliases[T](current: T, primary: T, legacy: tuple[T, ...]) -> tuple[T, ...]:
    """Return *current* plus legacy aliases when using the default primary name."""
    if current != primary:
        return (current,)
    return (current, *tuple(item for item in legacy if item != current))


def preferred_existing_path(current: Path, primary: Path, legacy: tuple[Path, ...]) -> Path:
    """Prefer an existing legacy path when the primary default has not been created yet."""
    if current != primary or current.exists():
        return current

    for candidate in legacy:
        if candidate.exists():
            return candidate

    return current
