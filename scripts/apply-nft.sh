#!/usr/bin/env bash
set -euo pipefail

GROUP_NAME="antigravity-warp"
REDIRECT_PORT="12345"

if ! command -v nft >/dev/null 2>&1; then
  echo "nft not found" >&2
  exit 1
fi

if ! getent group "$GROUP_NAME" >/dev/null 2>&1; then
  groupadd --system "$GROUP_NAME"
fi

GID="$(getent group "$GROUP_NAME" | cut -d: -f3)"

nft delete table inet ag_warp 2>/dev/null || true

nft -f - <<NFT
table inet ag_warp {
  chain output {
    type nat hook output priority -100; policy accept;

    meta skgid $GID ip daddr 127.0.0.0/8 return
    meta skgid $GID ip daddr 10.0.0.0/8 return
    meta skgid $GID ip daddr 100.64.0.0/10 return
    meta skgid $GID ip daddr 169.254.0.0/16 return
    meta skgid $GID ip daddr 172.16.0.0/12 return
    meta skgid $GID ip daddr 192.168.0.0/16 return
    meta skgid $GID ip daddr 172.17.0.0/16 return
    meta skgid $GID ip daddr 172.18.0.0/16 return
    meta skgid $GID ip daddr 172.19.0.0/16 return

    meta skgid $GID tcp dport { 80, 443 } redirect to :$REDIRECT_PORT
  }

  chain output_filter {
    type filter hook output priority 0; policy accept;

    meta skgid $GID ip6 daddr ::1/128 accept
    meta skgid $GID ip6 daddr fe80::/10 accept
    meta skgid $GID ip6 daddr fc00::/7 accept
    meta skgid $GID ip6 nexthdr tcp reject with tcp reset
    meta skgid $GID ip6 nexthdr udp reject
  }
}
NFT

echo "Applied nftables table inet ag_warp for group $GROUP_NAME (gid $GID)."
echo "Dry-run:"
echo "setpriv --regid $GID --clear-groups curl -4 https://www.cloudflare.com/cdn-cgi/trace"
