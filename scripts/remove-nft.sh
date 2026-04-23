#!/usr/bin/env bash
set -euo pipefail

if command -v nft >/dev/null 2>&1; then
  nft delete table inet ag_warp 2>/dev/null || true
fi

echo "Removed nftables table inet ag_warp if it existed."
