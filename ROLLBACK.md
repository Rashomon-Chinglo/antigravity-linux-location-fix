# Rollback Guide

This project is designed so every runtime change has a direct rollback.

## Full Rollback

Run:

```bash
cd /root/Project/cloud_workspace/antigravity-warp-gid
sudo ./scripts/disable-antigravity-wrapper.sh
sudo ./scripts/remove-nft.sh
sudo ./scripts/stop-pm2-service.sh
sudo systemctl stop sing-box-ag-warp
sudo systemctl disable sing-box-ag-warp
warp-cli --accept-tos disconnect
```

Optional cleanup:

```bash
sudo rm -f /etc/systemd/system/sing-box-ag-warp.service
sudo rm -f /etc/sing-box/ag-warp.json
sudo systemctl daemon-reload
```

The `antigravity-warp` group may be left in place safely. If you want to remove it:

```bash
sudo groupdel antigravity-warp
```

Only remove the group after confirming no process uses it:

```bash
ps -eo pid,user,group,args | rg antigravity-warp
```

## Per-Change Rollback

### WARP Proxy Mode

Applied by:

```bash
sudo ./scripts/start-warp-proxy.sh
```

Changes:

```text
WARP mode -> proxy
WARP proxy port -> 40000
WARP connected
```

Check:

```bash
warp-cli --accept-tos status
warp-cli --accept-tos settings
ss -ltnp | rg 40000
```

Rollback:

```bash
warp-cli --accept-tos disconnect
```

If desired, manually set WARP back to another mode:

```bash
warp-cli --accept-tos mode proxy
```

### sing-box Service

Applied by systemd:

```bash
sudo ./scripts/install-systemd-service.sh
```

Applied by PM2:

```bash
sudo ./scripts/start-pm2-service.sh
```

Changes:

```text
PM2 mode:
Starts PM2 app sing-box-ag-warp from pm2/ecosystem.config.cjs.

systemd mode:
/etc/sing-box/ag-warp.json
/etc/systemd/system/sing-box-ag-warp.service
systemd service enabled and started
```

Check:

```bash
systemctl status sing-box-ag-warp --no-pager
pm2 status sing-box-ag-warp
ss -ltnp | rg 12345
```

Rollback:

```bash
sudo ./scripts/stop-pm2-service.sh
sudo systemctl stop sing-box-ag-warp
sudo systemctl disable sing-box-ag-warp
sudo rm -f /etc/systemd/system/sing-box-ag-warp.service
sudo rm -f /etc/sing-box/ag-warp.json
sudo systemctl daemon-reload
```

### nftables Rules

Applied by:

```bash
sudo ./scripts/apply-nft.sh
```

Changes:

```text
Creates group antigravity-warp if missing.
Creates nftables table inet ag_warp.
Redirects antigravity-warp GID public IPv4 TCP 80/443 to 127.0.0.1:12345.
Rejects public IPv6 TCP/UDP for antigravity-warp GID.
```

Check:

```bash
sudo nft list table inet ag_warp
getent group antigravity-warp
```

Rollback:

```bash
sudo ./scripts/remove-nft.sh
```

Optional group removal:

```bash
sudo groupdel antigravity-warp
```

### Antigravity Wrapper

Applied by:

```bash
sudo ./scripts/enable-antigravity-wrapper.sh
```

Changes:

```text
Renames:
/root/.antigravity-server/bin/1.23.2-15487b3041e65228cae24980a3f796c905ef582c/bin/antigravity-server

To:
/root/.antigravity-server/bin/1.23.2-15487b3041e65228cae24980a3f796c905ef582c/bin/antigravity-server.real

Creates wrapper at original antigravity-server path.
```

Check:

```bash
grep -n "antigravity-warp wrapper" \
  /root/.antigravity-server/bin/1.23.2-15487b3041e65228cae24980a3f796c905ef582c/bin/antigravity-server

ls -l /root/.antigravity-server/bin/1.23.2-15487b3041e65228cae24980a3f796c905ef582c/bin/antigravity-server*
```

Rollback:

```bash
sudo ./scripts/disable-antigravity-wrapper.sh
```

## Safety Checks

After rollback:

```bash
cd /root/Project/cloud_workspace/antigravity-warp-gid
./scripts/check.sh
```

Expected:

```text
WARP disconnected or only proxy mode if intentionally left connected
sing-box-ag-warp inactive
nft table inet ag_warp not present
Antigravity wrapper disabled
cloudflared active
```
