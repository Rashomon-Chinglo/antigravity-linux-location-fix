"""Allow running as `python -m ag_warp`."""

# nuitka-project-if: {OS} == "Linux":
#    nuitka-project: --output-filename=ag-warp

from ag_warp.cli import app


def main() -> None:
    """Program entrypoint for both Python and Nuitka execution."""
    app()


main()
