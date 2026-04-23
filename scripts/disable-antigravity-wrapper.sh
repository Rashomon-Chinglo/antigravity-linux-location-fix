#!/usr/bin/env bash
set -euo pipefail

SERVER_DIR="/root/.antigravity-server/bin/1.23.2-15487b3041e65228cae24980a3f796c905ef582c/bin"
SERVER="$SERVER_DIR/antigravity-server"
REAL="$SERVER_DIR/antigravity-server.real"

if [[ ! -e "$REAL" ]]; then
  echo "No antigravity-server.real found; wrapper is probably not enabled."
  exit 0
fi

if [[ -e "$SERVER" ]] && ! grep -q "antigravity-warp wrapper" "$SERVER" 2>/dev/null; then
  echo "Current launcher is not this project's wrapper; refusing to overwrite:" >&2
  echo "$SERVER" >&2
  exit 1
fi

rm -f "$SERVER"
mv "$REAL" "$SERVER"
chmod 0755 "$SERVER"

echo "Restored original Antigravity server launcher."
