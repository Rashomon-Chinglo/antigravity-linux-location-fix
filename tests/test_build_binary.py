"""Tests for the local Nuitka build helper."""

from pathlib import Path

from tools.build_binary import ENTRYPOINT, OUTPUT_DIR, RICH_INCLUDE_PACKAGE, build_command


def test_build_command_includes_expected_nuitka_flags() -> None:
    cmd = build_command("/usr/bin/python3")

    assert cmd[:3] == ["/usr/bin/python3", "-m", "nuitka"]
    assert "--mode=onefile" in cmd
    assert f"--output-dir={OUTPUT_DIR}" in cmd
    assert f"--include-package={RICH_INCLUDE_PACKAGE}" in cmd
    assert cmd[-1] == str(ENTRYPOINT)


def test_main_entrypoint_keeps_required_nuitka_project_options() -> None:
    content = Path(ENTRYPOINT).read_text()

    assert "--output-filename=ag-wrap" in content
    assert "--include-package=rich._unicode_data" in content
