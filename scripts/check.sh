#!/usr/bin/env bash
set -euo pipefail

echo "== WARP =="
if command -v warp-cli >/dev/null 2>&1; then
  warp-cli --accept-tos status || true
  warp-cli --accept-tos settings | sed -n '1,40p' || true
else
  echo "warp-cli not found"
fi

echo
echo "== sing-box-ag-warp systemd =="
systemctl is-active sing-box-ag-warp 2>/dev/null || true
systemctl status sing-box-ag-warp --no-pager 2>/dev/null | sed -n '1,18p' || true

echo
echo "== sing-box-ag-warp PM2 =="
if command -v pm2 >/dev/null 2>&1; then
  pm2 status sing-box-ag-warp || true
else
  echo "pm2 not found"
fi

echo
echo "== nft ag_warp =="
if command -v nft >/dev/null 2>&1; then
  nft list table inet ag_warp 2>/dev/null || echo "table inet ag_warp not present"
else
  echo "nft not found"
fi

echo
echo "== Antigravity wrapper =="
SERVER="/root/.antigravity-server/bin/1.23.2-15487b3041e65228cae24980a3f796c905ef582c/bin/antigravity-server"
REAL="$SERVER.real"
if [[ -e "$SERVER" ]] && grep -q "antigravity-warp wrapper" "$SERVER" 2>/dev/null; then
  echo "wrapper enabled"
elif [[ -e "$REAL" ]]; then
  echo "real server exists, but wrapper marker not found"
else
  echo "wrapper disabled"
fi

echo
echo "== Antigravity processes =="
ps -eo pid,ppid,user,group,args | rg 'antigravity|language_server|extensionHost' || true

echo
echo "== Listeners =="
ss -ltnp 2>/dev/null | rg '12345|40000|sing-box|warp' || true
