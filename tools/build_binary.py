"""Build a Linux onefile binary with Nuitka."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "src" / "ag_warp" / "__main__.py"
OUTPUT_DIR = ROOT / "dist" / "nuitka"


def main() -> int:
    """Compile the project into a Linux onefile binary."""
    compiler = _detect_compiler()
    if compiler is None:
        print("No supported C compiler found. Install gcc, clang, or zig first.", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--mode=onefile",
        "--assume-yes-for-downloads",
        f"--output-dir={OUTPUT_DIR}",
        str(ENTRYPOINT),
    ]

    print(f"Using compiler: {compiler}")
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)

    binary_path = OUTPUT_DIR / "ag-warp"
    print(f"Built binary: {binary_path}")
    return 0


def _detect_compiler() -> str | None:
    """Return the first supported compiler found on PATH."""
    for compiler in ("gcc", "clang", "zig"):
        if shutil.which(compiler):
            return compiler
    return None


if __name__ == "__main__":
    raise SystemExit(main())
