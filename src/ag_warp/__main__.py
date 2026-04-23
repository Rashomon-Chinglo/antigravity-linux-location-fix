"""Allow running as `python -m ag_warp`."""

# nuitka-project-if: {OS} == "Linux":
#    nuitka-project: --output-filename=ag-wrap
#    nuitka-project: --include-package=rich._unicode_data

from ag_warp.cli import app


def main() -> None:
    """Program entrypoint for both Python and Nuitka execution."""
    app()


main()
