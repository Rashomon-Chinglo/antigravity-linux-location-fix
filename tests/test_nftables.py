"""Tests for ag_warp.nftables rule generation."""

from ag_warp.config import NftablesConfig
from ag_warp.nftables import generate_rules


def test_basic_rules() -> None:
    cfg = NftablesConfig()
    rules = generate_rules(cfg, gid=987, redirect_port=12345)

    assert "meta skgid 987" in rules
    assert "tcp dport { 80, 443 }" in rules
    assert "redirect to :12345" in rules
    assert "127.0.0.0/8" in rules
    assert "172.16.0.0/12" in rules


def test_ipv6_blocking() -> None:
    cfg = NftablesConfig(block_public_ipv6=True)
    rules = generate_rules(cfg, gid=987, redirect_port=12345)

    assert "ip6 nexthdr tcp reject with tcp reset" in rules
    assert "ip6 nexthdr udp reject" in rules
    assert "ip6 daddr ::1 accept" in rules
    assert "ip6 daddr fe80::/10 accept" in rules


def test_quic_blocking() -> None:
    cfg = NftablesConfig(block_udp_ports=[443])
    rules = generate_rules(cfg, gid=987, redirect_port=12345)

    assert "udp dport { 443 } drop" in rules


def test_docker_cidrs() -> None:
    cfg = NftablesConfig()
    docker = ["172.17.0.0/16", "172.18.0.0/16"]
    rules = generate_rules(cfg, gid=987, redirect_port=12345, docker_cidrs=docker)

    assert "172.17.0.0/16" in rules
    assert "172.18.0.0/16" in rules


def test_extra_bypass() -> None:
    cfg = NftablesConfig(extra_bypass_cidrs=["203.0.113.0/24"])
    rules = generate_rules(cfg, gid=987, redirect_port=12345)

    assert "203.0.113.0/24" in rules


def test_no_ipv6_blocking() -> None:
    cfg = NftablesConfig(block_public_ipv6=False)
    rules = generate_rules(cfg, gid=987, redirect_port=12345)

    assert "ip6" not in rules


def test_custom_ports() -> None:
    cfg = NftablesConfig(redirect_tcp_ports=[80, 443, 8443])
    rules = generate_rules(cfg, gid=987, redirect_port=12345)

    assert "tcp dport { 80, 443, 8443 }" in rules
