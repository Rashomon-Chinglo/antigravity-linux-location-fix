#!/usr/bin/env bash
set -euo pipefail

GROUP_NAME="antigravity-warp"
SERVER_DIR="/root/.antigravity-server/bin/1.23.2-15487b3041e65228cae24980a3f796c905ef582c/bin"
SERVER="$SERVER_DIR/antigravity-server"
REAL="$SERVER_DIR/antigravity-server.real"

if ! command -v setpriv >/dev/null 2>&1; then
  echo "setpriv not found" >&2
  exit 1
fi

if ! getent group "$GROUP_NAME" >/dev/null 2>&1; then
  groupadd --system "$GROUP_NAME"
fi

if [[ ! -e "$SERVER" ]]; then
  echo "Antigravity server not found: $SERVER" >&2
  exit 1
fi

if [[ -e "$REAL" ]]; then
  if grep -q "antigravity-warp wrapper" "$SERVER" 2>/dev/null; then
    echo "Wrapper already enabled: $SERVER"
    exit 0
  fi
  echo "Real server already exists but current launcher is not our wrapper: $REAL" >&2
  exit 1
fi

mv "$SERVER" "$REAL"

cat > "$SERVER" <<'EOF'
#!/usr/bin/env bash
# antigravity-warp wrapper
set -euo pipefail

GROUP_NAME="antigravity-warp"
REAL="/root/.antigravity-server/bin/1.23.2-15487b3041e65228cae24980a3f796c905ef582c/bin/antigravity-server.real"
GID="$(getent group "$GROUP_NAME" | cut -d: -f3)"

exec /usr/bin/setpriv \
  --regid "$GID" \
  --clear-groups \
  "$REAL" "$@"
EOF

chmod 0755 "$SERVER"

echo "Enabled Antigravity wrapper."
echo "Restart/reload Antigravity Remote SSH so it starts through the wrapper."
