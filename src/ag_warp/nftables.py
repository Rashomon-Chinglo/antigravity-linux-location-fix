"""nftables rule generation and application."""

from __future__ import annotations

from ag_warp.branding import DEFAULT_NFT_TABLE_NAME, LEGACY_NFT_TABLE_NAMES, with_legacy_aliases
from ag_warp.config import NftablesConfig
from ag_warp.shell import Shell
from ag_warp.ui import console

# RFC1918 + loopback + CGN + link-local — always bypassed.
_BUILTIN_BYPASS: list[str] = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "100.64.0.0/10",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.168.0.0/16",
]


def generate_rules(
    config: NftablesConfig,
    gid: int,
    redirect_port: int,
    docker_cidrs: list[str] | None = None,
) -> str:
    """Render the nftables ruleset as a string."""
    bypass_cidrs = _build_bypass_cidrs(config, docker_cidrs)
    bypass_lines = _render_bypass_rules(gid, bypass_cidrs)
    filter_body = _render_filter_body(config, gid)
    tcp_ports = ", ".join(str(p) for p in config.redirect_tcp_ports)

    ruleset = f"""\
table {config.table_family} {config.table_name} {{
  chain output {{
    type nat hook output priority dstnat; policy accept;

{bypass_lines}

    meta skgid {gid} tcp dport {{ {tcp_ports} }} redirect to :{redirect_port}
  }}

  chain output_filter {{
    type filter hook output priority filter; policy accept;

{filter_body}
  }}
}}
"""
    return ruleset


def _build_bypass_cidrs(
    config: NftablesConfig,
    docker_cidrs: list[str] | None,
) -> list[str]:
    """Merge builtin, Docker, and user-defined bypass CIDRs."""
    all_bypass = list(_BUILTIN_BYPASS)
    if docker_cidrs:
        all_bypass.extend(docker_cidrs)
    all_bypass.extend(config.extra_bypass_cidrs)
    return _deduplicate(all_bypass)


def _render_bypass_rules(gid: int, cidrs: list[str]) -> str:
    """Render the nftables bypass rules for the given CIDRs."""
    return "\n".join(f"    meta skgid {gid} ip daddr {cidr} return" for cidr in cidrs)


def _render_filter_body(config: NftablesConfig, gid: int) -> str:
    """Render the filter-chain body sections."""
    sections = [
        _render_ipv6_block(config, gid),
        _render_udp_block(config, gid),
    ]
    return "\n".join(section for section in sections if section)


def _render_udp_block(config: NftablesConfig, gid: int) -> str:
    """Render UDP blocking rules when configured."""
    if not config.block_udp_ports:
        return ""
    udp_ports = ", ".join(str(p) for p in config.block_udp_ports)
    return f"    meta skgid {gid} udp dport {{ {udp_ports} }} drop"


def _render_ipv6_block(config: NftablesConfig, gid: int) -> str:
    """Render IPv6 filtering rules when enabled."""
    if not config.block_public_ipv6:
        return ""
    return "\n".join(
        [
            f"    meta skgid {gid} ip6 daddr ::1 accept",
            f"    meta skgid {gid} ip6 daddr fe80::/10 accept",
            f"    meta skgid {gid} ip6 daddr fc00::/7 accept",
            f"    meta skgid {gid} ip6 nexthdr tcp reject with tcp reset",
            f"    meta skgid {gid} ip6 nexthdr udp reject with icmpv6 port-unreachable",
        ]
    )


def _deduplicate(items: list[str]) -> list[str]:
    """Deduplicate a list while preserving its original order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def apply_rules(
    config: NftablesConfig,
    gid: int,
    redirect_port: int,
    shell: Shell,
    docker_cidrs: list[str] | None = None,
) -> None:
    """Apply nftables rules, replacing any existing table."""
    rules = generate_rules(config, gid, redirect_port, docker_cidrs)

    # Delete existing tables first (ignore error if absent).
    for table_name in _managed_table_names(config):
        shell.run(["nft", "delete", "table", config.table_family, table_name], check=False)

    console.print(f"  Applying nftables table {config.table_family} {config.table_name} …")
    shell.run(["nft", "-f", "-"], input_text=rules)


def remove_rules(config: NftablesConfig, shell: Shell) -> None:
    """Remove the nftables table."""
    for table_name in _managed_table_names(config):
        console.print(f"  Removing nftables table {config.table_family} {table_name} …")
        shell.run(["nft", "delete", "table", config.table_family, table_name], check=False)


def table_exists(config: NftablesConfig, shell: Shell) -> bool:
    """Check whether the nftables table exists."""
    return active_table_name(config, shell) is not None


def active_table_name(config: NftablesConfig, shell: Shell) -> str | None:
    """Return the active table name, including legacy aliases."""
    for table_name in _managed_table_names(config):
        r = shell.run_read(["nft", "list", "table", config.table_family, table_name])
        if r.returncode == 0:
            return table_name
    return None


def _managed_table_names(config: NftablesConfig) -> tuple[str, ...]:
    return with_legacy_aliases(
        config.table_name,
        DEFAULT_NFT_TABLE_NAME,
        LEGACY_NFT_TABLE_NAMES,
    )
