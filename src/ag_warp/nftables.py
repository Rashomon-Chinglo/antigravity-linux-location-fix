"""nftables rule generation and application."""

from __future__ import annotations

from ag_warp.config import NftablesConfig
from ag_warp.shell import Shell, console

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
    # Merge bypass CIDRs: builtins + docker + user-specified.
    all_bypass = list(_BUILTIN_BYPASS)
    if docker_cidrs:
        all_bypass.extend(docker_cidrs)
    all_bypass.extend(config.extra_bypass_cidrs)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    bypass_cidrs: list[str] = []
    for cidr in all_bypass:
        if cidr not in seen:
            seen.add(cidr)
            bypass_cidrs.append(cidr)

    # Build bypass lines.
    bypass_lines = "\n".join(
        f"    meta skgid {gid} ip daddr {cidr} return" for cidr in bypass_cidrs
    )

    # TCP redirect ports.
    tcp_ports = ", ".join(str(p) for p in config.redirect_tcp_ports)

    # UDP block section.
    udp_block = ""
    if config.block_udp_ports:
        udp_ports = ", ".join(str(p) for p in config.block_udp_ports)
        udp_block = f"    meta skgid {gid} udp dport {{ {udp_ports} }} drop"

    # IPv6 block section.
    ipv6_block = ""
    if config.block_public_ipv6:
        ipv6_block = "\n".join(
            [
                f"    meta skgid {gid} ip6 daddr ::1 accept",
                f"    meta skgid {gid} ip6 daddr fe80::/10 accept",
                f"    meta skgid {gid} ip6 daddr fc00::/7 accept",
                f"    meta skgid {gid} ip6 nexthdr tcp reject with tcp reset",
                f"    meta skgid {gid} ip6 nexthdr udp reject with icmpv6 port-unreachable",
            ]
        )

    # Assemble filter chain body.
    filter_body_parts: list[str] = []
    if ipv6_block:
        filter_body_parts.append(ipv6_block)
    if udp_block:
        filter_body_parts.append(udp_block)
    filter_body = "\n".join(filter_body_parts)

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


def apply_rules(
    config: NftablesConfig,
    gid: int,
    redirect_port: int,
    shell: Shell,
    docker_cidrs: list[str] | None = None,
) -> None:
    """Apply nftables rules, replacing any existing table."""
    rules = generate_rules(config, gid, redirect_port, docker_cidrs)

    # Delete existing table first (ignore error if absent).
    shell.run(
        ["nft", "delete", "table", config.table_family, config.table_name],
        check=False,
    )

    console.print(f"  Applying nftables table {config.table_family} {config.table_name} …")
    shell.run(["nft", "-f", "-"], input_text=rules)


def remove_rules(config: NftablesConfig, shell: Shell) -> None:
    """Remove the nftables table."""
    console.print(f"  Removing nftables table {config.table_family} {config.table_name} …")
    shell.run(
        ["nft", "delete", "table", config.table_family, config.table_name],
        check=False,
    )


def table_exists(config: NftablesConfig, shell: Shell) -> bool:
    """Check whether the nftables table exists."""
    r = shell.run_read(
        [
            "nft",
            "list",
            "table",
            config.table_family,
            config.table_name,
        ]
    )
    return r.returncode == 0
