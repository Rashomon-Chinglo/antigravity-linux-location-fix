# Fix Antigravity Remote SSH FAILED_PRECONDITION on Linux VPS

[![Release](https://img.shields.io/github/v/release/Rashomon-Chinglo/antigravity-linux-location-fix)](https://github.com/Rashomon-Chinglo/antigravity-linux-location-fix/releases)
[![License](https://img.shields.io/github/license/Rashomon-Chinglo/antigravity-linux-location-fix)](https://github.com/Rashomon-Chinglo/antigravity-linux-location-fix/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-linux-lightgrey)](https://github.com/Rashomon-Chinglo/antigravity-linux-location-fix)

`antigravity-linux-location-fix` solves the Antigravity Remote SSH error `"User location is not supported for the API use."` (`FAILED_PRECONDITION`) on Linux VPS providers such as Contabo, Hetzner, and OVH.

It works by routing only the Antigravity remote server process tree through Cloudflare WARP with Linux GID-based `nftables` rules. Everything else on the host stays on the normal network path.

## Problem

Typical symptoms:

- Antigravity Remote SSH connects, but model/API calls fail with `FAILED_PRECONDITION`
- Logs contain `User location is not supported for the API use.`
- Full-host WARP fixes the API issue but breaks unrelated services like `cloudflared`, SSH, Docker, or normal server networking

This project is for the case where you need a targeted Antigravity location fix on Linux without forcing the whole machine through WARP.

## Solution

```text
antigravity-server (wrapper)
  → setpriv --regid <GID> (antigravity-warp group)
    → antigravity-server.real
      → extension host / language_server
        → Google API requests

Kernel nftables:
  if process GID == antigravity-warp
  and destination is public IPv4 TCP 80/443
  → redirect to sing-box (:12345)
    → WARP proxy (:40000)
      → Cloudflare egress
```

Why this is useful:

- Only Antigravity traffic is intercepted
- `cloudflared`, SSH, Docker, and other host services stay direct
- The workflow is idempotent and designed for rollback
- The project supports `dry-run`, `status`, `doctor`, and `verify`

## Download

### Prebuilt Linux Binary

Download the latest Linux `x86_64` binary from:

- [GitHub Releases](https://github.com/Rashomon-Chinglo/antigravity-linux-location-fix/releases)

Release assets are published with names like:

```text
ag-warp-v1.0.1-linux-x86_64
```

### Install from Source

```bash
uv tool install git+https://github.com/Rashomon-Chinglo/antigravity-linux-location-fix.git
```

Or:

```bash
git clone https://github.com/Rashomon-Chinglo/antigravity-linux-location-fix.git
cd antigravity-linux-location-fix
uv sync
```

## Prerequisites

- Linux with `nftables`
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Cloudflare WARP](https://pkg.cloudflareclient.com/) as `warp-cli`
- [sing-box](https://sing-box.sagernet.org/)
- `setpriv`
- `nft`

Important:

- The binary removes the Python runtime requirement for end users
- It does not remove the system runtime requirements above
- Running `ag-warp on`, `off`, or `rollback` still requires appropriate Linux permissions

## Quick Start

```bash
# Check runtime dependencies
ag-warp doctor

# Preview changes
ag-warp on --dry-run

# Apply changes
ag-warp on

# Or apply non-interactively
ag-warp on --yes

# Verify the routing chain end-to-end
ag-warp verify
```

## Commands

| Command | Description |
|---------|-------------|
| `ag-warp status` | Read-only status check of all components |
| `ag-warp on` | Start and converge all components to desired state |
| `ag-warp apply` | Alias for `on` |
| `ag-warp off` | Stop runtime interception while keeping wrapper/state |
| `ag-warp rollback` | Full rollback: `off` + safe wrapper restore |
| `ag-warp verify` | End-to-end verification |
| `ag-warp doctor` | Check dependencies |
| `ag-warp dump-config` | Print final merged configuration |

Common flags:

```bash
--config PATH
--dry-run
--yes / -y
```

## Configuration

Create `config.json` and override only what you need:

```json
{
  "supervisor": {
    "backend": "pm2"
  },
  "warp": {
    "proxy_port": 50000
  }
}
```

See [config.example.json](config.example.json) for all fields.

Use:

```bash
ag-warp dump-config
```

to inspect the final merged config.

## Safety

- Operations are designed to be idempotent
- Wrapper injection requires confirmation by default
- `off` preserves wrapper state but disables interception
- `rollback` safely restores the original binary when checks pass
- `cloudflared` is never modified
- WARP is used in proxy mode, not as full-host mode

## Binary Build

This repository can publish a Linux onefile binary with Nuitka.

Local build:

```bash
uv run --with nuitka==4.0.5 python tools/build_binary.py
```

Expected output:

```text
dist/nuitka/ag-warp
```

Notes:

- Nuitka requires a C compiler such as `gcc` or `clang`
- The local build helper checks for a compiler before compiling

## GitHub Release Build

The workflow [nuitka-release.yml](.github/workflows/nuitka-release.yml) does the following:

1. Runs `pytest` and `ruff`
2. Builds a Linux `x86_64` onefile binary with Nuitka
3. Uploads the binary as a GitHub Actions artifact
4. On tag pushes like `v1.0.1`, creates or updates the matching GitHub Release and uploads the binary there

To publish a release binary:

```bash
git tag v1.0.1
git push origin v1.0.1
```

After the workflow finishes, the binary appears on the repository Releases page.

## Development

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run python -m ag_warp --help
```

## Notes for Contributors

Compared with the original MVP release (`v0.0.0`), the current project no longer ships repo-local shell scripts or static PM2/systemd templates. The Python CLI is the source of truth for generated config, supervisor definitions, `nftables` rules, and wrapper handling.

## License

MIT
