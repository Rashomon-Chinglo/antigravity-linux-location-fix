#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v pm2 >/dev/null 2>&1; then
  echo "pm2 not found" >&2
  exit 1
fi

if ! command -v sing-box >/dev/null 2>&1; then
  echo "sing-box not found" >&2
  exit 1
fi

sing-box check -c "$PROJECT_DIR/configs/sing-box-ag-warp.json"
pm2 start "$PROJECT_DIR/pm2/ecosystem.config.cjs" --only sing-box-ag-warp
pm2 save
pm2 status sing-box-ag-warp

echo
echo "If PM2 startup is not already configured for this host, run:"
echo "pm2 startup"
