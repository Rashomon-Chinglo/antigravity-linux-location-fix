# antigravity-linux-location-fix

Fix for `"User location is not supported for the API use."` (`FAILED_PRECONDITION`) when running **Antigravity Remote SSH** on Linux VPS (Contabo, Hetzner, OVH, etc.)

## What this does

Routes **only** the Antigravity Remote SSH process tree through Cloudflare WARP, using Linux GID-based nftables rules. All other host services (cloudflared, Docker, SSH, web servers) remain on the normal network path.

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

## Prerequisites

- Linux with nftables (kernel 4.x+)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Cloudflare WARP](https://pkg.cloudflareclient.com/) (`warp-cli`)
- [sing-box](https://sing-box.sagernet.org/)
- `setpriv` (usually from `util-linux`)
- `nft` (from `nftables`)

## Install

```bash
# From GitHub
uv tool install git+https://github.com/Rashomon-Chinglo/antigravity-linux-location-fix.git

# Or clone and install locally
git clone https://github.com/Rashomon-Chinglo/antigravity-linux-location-fix.git
cd antigravity-linux-location-fix
uv sync
```

## Quick start

```bash
# Check system dependencies
ag-warp doctor

# Preview what will happen
ag-warp on --dry-run

# Apply (interactive confirmation for wrapper injection)
ag-warp on

# Or apply without prompts
ag-warp on --yes

# Verify the routing chain end-to-end
ag-warp verify
```

## Commands

| Command | Description |
|---------|-------------|
| `ag-warp status` | Read-only check of all components |
| `ag-warp on` | Start and converge all components to desired state |
| `ag-warp apply` | Alias for `on` |
| `ag-warp off` | Stop runtime interception (keeps wrapper) |
| `ag-warp rollback` | Full rollback: `off` + safe wrapper restore |
| `ag-warp verify` | End-to-end routing verification |
| `ag-warp doctor` | Check system dependencies |
| `ag-warp dump-config` | Print final merged configuration |

### Common flags

```bash
--config PATH    # Use custom config file
--dry-run        # Print planned changes, don't execute
--yes / -y       # Skip interactive confirmations
```

## Configuration

Create `config.json` (only include fields you want to override):

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

See [`config.example.json`](config.example.json) for all available options.

Use `ag-warp dump-config` to see the final merged configuration.

## How it works

1. **GID tagging**: The Antigravity binary is wrapped with a script that sets the process group to `antigravity-warp` via `setpriv --regid`.

2. **Kernel-level interception**: nftables rules match outbound TCP 80/443 traffic from processes with the `antigravity-warp` GID and redirect it to a local sing-box instance.

3. **WARP proxy**: sing-box forwards the intercepted traffic through Cloudflare WARP (running in proxy mode), which egresses from a Cloudflare IP that is in a supported region.

4. **Zero collateral damage**: Only processes in the `antigravity-warp` group are affected. Everything else — cloudflared, Docker services, SSH — goes through the normal network path.

## Safety

- All operations are **idempotent** — safe to run multiple times.
- Wrapper injection requires **interactive confirmation** by default.
- Rollback uses **four-check verification** before restoring binaries.
- `off` stops interception but **preserves the wrapper** (harmless without nftables).
- cloudflared is **never modified**.
- WARP is **never** set to full-host mode.

## Rollback

```bash
# Stop interception (keeps wrapper)
ag-warp off

# Full rollback (stops interception + restores original binary)
ag-warp rollback
```

## Development

```bash
uv sync
uv run ag-warp status
uv run pytest
uv run ruff check .
uv run ruff format .
```

## License

MIT
