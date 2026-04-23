#!/usr/bin/env bash
set -euo pipefail

if ! command -v pm2 >/dev/null 2>&1; then
  echo "pm2 not found" >&2
  exit 0
fi

pm2 delete sing-box-ag-warp || true
pm2 save
