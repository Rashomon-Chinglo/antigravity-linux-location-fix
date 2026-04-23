#!/usr/bin/env bash
set -euo pipefail

if ! command -v warp-cli >/dev/null 2>&1; then
  echo "warp-cli not found" >&2
  exit 1
fi

warp-cli --accept-tos tunnel protocol set MASQUE
warp-cli --accept-tos proxy port 40000
warp-cli --accept-tos mode proxy
warp-cli --accept-tos connect

echo "WARP status:"
warp-cli --accept-tos status
echo
echo "Verify with:"
echo "curl -x http://127.0.0.1:40000 https://www.cloudflare.com/cdn-cgi/trace"
