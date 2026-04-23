# AGENTS.md

## Project Purpose

This repository fixes the Antigravity Remote SSH Linux VPS error:

```text
User location is not supported for the API use.
FAILED_PRECONDITION
```

The project routes only the Antigravity process tree through Cloudflare WARP by using a dedicated Linux group plus `nftables` redirect rules.

## Key Rules

- Keep the project Linux-first
- Do not reintroduce the old MVP shell-script deployment model
- The Python CLI is the source of truth for runtime generation
- Preserve `dry-run`, idempotence, and rollback behavior
- Avoid changes that force full-host WARP routing

## Repository Layout

- `src/ag_warp/cli.py`: Typer CLI entrypoints
- `src/ag_warp/engine.py`: high-level workflows
- `src/ag_warp/config.py`: config model and merge logic
- `src/ag_warp/supervisor.py`: systemd and PM2 handling
- `src/ag_warp/nftables.py`: rule generation and application
- `src/ag_warp/warp.py`: `warp-cli` integration
- `src/ag_warp/wrapper.py`: Antigravity wrapper injection and restore
- `src/ag_warp/verify.py`: end-to-end verification checks
- `tools/build_binary.py`: local Nuitka build helper
- `.github/workflows/nuitka-release.yml`: GitHub binary release workflow

## Common Commands

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
env UV_CACHE_DIR=/tmp/uv-cache uv run python -m ag_warp --help
env UV_CACHE_DIR=/tmp/uv-cache uv run ag-warp status
env UV_CACHE_DIR=/tmp/uv-cache uv run ag-warp on --dry-run
```

## Binary Release Flow

1. Update version strings in `pyproject.toml` and `src/ag_warp/__init__.py`
2. Commit and push changes
3. Create and push a tag like `v1.0.1`
4. GitHub Actions builds `ag-warp-<tag>-linux-x86_64`
5. The workflow uploads the binary to the matching GitHub Release

## Runtime Dependencies

The binary does not remove the need for these host tools:

- `warp-cli`
- `sing-box`
- `nft`
- `setpriv`
- Linux privileges required by the chosen command
