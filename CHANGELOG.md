# Change Log

This file records changes made by this project to the host.

Current state:

```text
Prepared only. No system changes have been applied by this project yet.
```

## 2026-04-23 - Project Created

Created files under:

```text
/root/Project/cloud_workspace/antigravity-warp-gid
```

Files:

```text
README.md
CHANGELOG.md
ROLLBACK.md
configs/sing-box-ag-warp.json
systemd/sing-box-ag-warp.service
pm2/ecosystem.config.cjs
scripts/start-warp-proxy.sh
scripts/install-systemd-service.sh
scripts/start-pm2-service.sh
scripts/stop-pm2-service.sh
scripts/apply-nft.sh
scripts/remove-nft.sh
scripts/enable-antigravity-wrapper.sh
scripts/disable-antigravity-wrapper.sh
scripts/check.sh
```

No original Antigravity, WARP, cloudflared, nftables, or systemd configuration was changed during project creation.

## Runtime Change Log

When applying the workaround, append entries here.

Template:

```text
Date:
Command:
Changed paths:
System state before:
System state after:
Verification:
Rollback command:
Notes:
```

## 2026-04-23 - Enabled PM2 WARP Proxy Routing For Antigravity

Date:

```text
2026-04-23
```

Commands:

```bash
cd /root/Project/cloud_workspace/antigravity-warp-gid
./scripts/start-warp-proxy.sh
./scripts/start-pm2-service.sh
./scripts/apply-nft.sh
./scripts/enable-antigravity-wrapper.sh
```

Changed system state:

```text
WARP was set to proxy mode and connected.
WARP proxy is listening on 127.0.0.1:40000.
PM2 app sing-box-ag-warp was started and saved.
sing-box-ag-warp is listening on 127.0.0.1:12345.
Group antigravity-warp was created with gid 987.
nftables table inet ag_warp was created.
Antigravity launcher was wrapped.
```

Changed paths:

```text
/root/.pm2/dump.pm2
/root/.antigravity-server/bin/1.23.2-15487b3041e65228cae24980a3f796c905ef582c/bin/antigravity-server
/root/.antigravity-server/bin/1.23.2-15487b3041e65228cae24980a3f796c905ef582c/bin/antigravity-server.real
```

Runtime services:

```text
PM2 app: sing-box-ag-warp
WARP proxy: 127.0.0.1:40000
sing-box transparent redirect: 127.0.0.1:12345
nftables table: inet ag_warp
Linux group: antigravity-warp gid 987
```

Verification:

```text
setpriv --regid 987 --clear-groups curl -4 https://www.cloudflare.com/cdn-cgi/trace -> warp=on
curl -4 https://www.cloudflare.com/cdn-cgi/trace -> warp=off
```

Rollback command:

```bash
cd /root/Project/cloud_workspace/antigravity-warp-gid
sudo ./scripts/disable-antigravity-wrapper.sh
sudo ./scripts/remove-nft.sh
sudo ./scripts/stop-pm2-service.sh
warp-cli --accept-tos disconnect
```

Notes:

```text
No full-host WARP routing was enabled.
cloudflared should remain outside the Antigravity-specific GID routing path.
Antigravity must be reloaded/reconnected so the remote server starts through the new wrapper.
```
