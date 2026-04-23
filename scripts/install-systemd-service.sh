#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v sing-box >/dev/null 2>&1; then
  echo "sing-box not found" >&2
  exit 1
fi

install -d -m 0755 /etc/sing-box
install -m 0644 "$PROJECT_DIR/configs/sing-box-ag-warp.json" /etc/sing-box/ag-warp.json
install -m 0644 "$PROJECT_DIR/systemd/sing-box-ag-warp.service" /etc/systemd/system/sing-box-ag-warp.service

sing-box check -c /etc/sing-box/ag-warp.json
systemctl daemon-reload
systemctl enable --now sing-box-ag-warp

systemctl status sing-box-ag-warp --no-pager
