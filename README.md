# Antigravity WARP GID Routing

This project documents and packages a targeted workaround for Antigravity Remote SSH
location errors on this VPS.

Goal:

```text
Only the Antigravity remote server process tree goes through Cloudflare WARP proxy.
cloudflared, sshd, Docker, and other host services stay on the normal Contabo network.
```

This avoids full-host WARP, which previously broke `cloudflared` and therefore SSH access.

## Architecture

```text
Antigravity Remote SSH starts:

bin/antigravity-server
  -> wrapper changes primary GID to antigravity-warp
  -> antigravity-server.real
  -> extension host
  -> extensions/antigravity/bin/language_server_linux_x64
  -> Google API requests

Kernel nftables:

if process GID == antigravity-warp
and destination is public IPv4 TCP 80/443
redirect to 127.0.0.1:12345

sing-box:

127.0.0.1:12345 transparent inbound
  -> WARP proxy at 127.0.0.1:40000
  -> Cloudflare WARP egress
```

Important: this does not use `HTTP_PROXY` as the primary enforcement mechanism.
Traffic is caught at the kernel routing/firewall layer by GID.

## Files

```text
configs/sing-box-ag-warp.json
  sing-box transparent redirect inbound. Outbound points to WARP proxy.

CHANGELOG.md
  Records what has been changed and includes a runtime change-log template.

ROLLBACK.md
  Detailed full and per-change rollback instructions.

systemd/sing-box-ag-warp.service
  systemd service for the sing-box transparent proxy.

pm2/ecosystem.config.cjs
  PM2 alternative for running sing-box instead of systemd.

scripts/start-warp-proxy.sh
  Sets WARP to proxy mode on 127.0.0.1:40000.

scripts/install-systemd-service.sh
  Installs and starts the sing-box service.

scripts/start-pm2-service.sh
  Starts the sing-box transparent proxy with PM2.

scripts/stop-pm2-service.sh
  Deletes the PM2-managed sing-box process.

scripts/apply-nft.sh
  Creates nftables rules that redirect antigravity-warp GID traffic.

scripts/remove-nft.sh
  Removes the nftables rules.

scripts/enable-antigravity-wrapper.sh
  Wraps the real antigravity-server so the whole process tree inherits GID antigravity-warp.

scripts/disable-antigravity-wrapper.sh
  Restores the original antigravity-server.

scripts/check.sh
  Shows WARP, sing-box, nftables, and Antigravity process status.
```

## Prerequisites

Already present on this VPS:

```text
warp-cli
sing-box
nft
setpriv
```

Check:

```bash
command -v warp-cli sing-box nft setpriv
```

## Recommended Rollout

Run commands from this project directory:

```bash
cd /root/Project/cloud_workspace/antigravity-warp-gid
```

### 1. Start WARP in proxy mode

```bash
sudo ./scripts/start-warp-proxy.sh
```

Verify WARP proxy:

```bash
curl -x http://127.0.0.1:40000 https://www.cloudflare.com/cdn-cgi/trace
```

Expected:

```text
warp=on
```

### 2. Start sing-box transparent proxy

Use either PM2 or systemd. PM2 is preferred if this server already uses PM2 for
long-running services.

PM2:

```bash
sudo ./scripts/start-pm2-service.sh
```

Check:

```bash
pm2 status sing-box-ag-warp
```

systemd alternative:

```bash
sudo ./scripts/install-systemd-service.sh
```

Check:

```bash
systemctl status sing-box-ag-warp --no-pager
```

### 3. Apply GID-based nftables redirect

```bash
sudo ./scripts/apply-nft.sh
```

### 4. Dry-run before touching Antigravity

This proves that only the special GID is routed through WARP.

```bash
sudo setpriv --regid "$(getent group antigravity-warp | cut -d: -f3)" --clear-groups \
  curl -4 https://www.cloudflare.com/cdn-cgi/trace
```

Expected:

```text
warp=on
```

Normal root traffic should remain non-WARP:

```bash
curl -4 https://www.cloudflare.com/cdn-cgi/trace
```

Expected:

```text
warp=off
```

If this dry-run fails, do not enable the Antigravity wrapper.

### 5. Enable Antigravity wrapper

```bash
sudo ./scripts/enable-antigravity-wrapper.sh
```

Then reconnect/reload Antigravity Remote SSH so it starts a fresh remote server.

### 6. Verify

```bash
./scripts/check.sh
```

After Antigravity starts, verify process group:

```bash
ps -eo pid,ppid,user,group,args | rg 'antigravity|language_server|extensionHost'
```

Expected Antigravity process tree group:

```text
antigravity-warp
```

Check logs:

```bash
rg -n 'daily-cloudcode|FAILED_PRECONDITION|User location|Parent pipe closed|ECONNREFUSED' \
  /root/.antigravity-server/data/logs -S
```

Good signs:

```text
No Parent pipe closed loop
No repeated 127.0.0.1 ECONNREFUSED
No User location is not supported
```

## Rollback

See `ROLLBACK.md` for the detailed rollback map.

```bash
cd /root/Project/cloud_workspace/antigravity-warp-gid
sudo ./scripts/disable-antigravity-wrapper.sh
sudo ./scripts/remove-nft.sh
sudo ./scripts/stop-pm2-service.sh
sudo systemctl stop sing-box-ag-warp 2>/dev/null || true
warp-cli --accept-tos disconnect
```

This project does not persist nftables rules across reboot. A reboot also clears the
runtime nftables table, but does not undo the Antigravity wrapper. Use the rollback
script to restore the launcher.

## Risks

This approach is safer than full-host WARP, but not risk-free.

```text
Antigravity updates may replace bin/antigravity-server and remove the wrapper.
Antigravity integrated terminal may inherit antigravity-warp GID and route HTTPS through WARP.
Only TCP is redirected. If a future Antigravity component uses UDP/QUIC, extra blocking may be needed.
Public IPv6 for antigravity-warp is rejected to force IPv4 fallback.
```

The important boundary is the whole `antigravity-server` process tree. Do not wrap only
`language_server_linux_x64`; that previously caused `Parent pipe closed` and
`ECONNREFUSED 127.0.0.1:<port>` loops.
