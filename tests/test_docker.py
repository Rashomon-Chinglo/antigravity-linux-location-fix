"""Tests for ag_warp.docker bridge discovery."""

import subprocess
from unittest.mock import patch

from ag_warp.docker import _try_ip_route_fallback
from ag_warp.shell import Shell


def test_ip_route_parsing() -> None:
    fake_output = """\
default via 217.217.252.1 dev eth0 proto static
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown
172.18.0.0/16 dev br-097001cefd20 proto kernel scope link src 172.18.0.1
172.19.0.0/16 dev br-2e0e8cd3df18 proto kernel scope link src 172.19.0.1
10.0.0.0/24 dev eth1 proto kernel scope link src 10.0.0.1
"""
    shell = Shell(dry_run=False)

    with patch.object(shell, "run_read") as mock:
        mock.return_value = subprocess.CompletedProcess(
            ["ip", "-4", "route"], 0, stdout=fake_output, stderr=""
        )
        cidrs = _try_ip_route_fallback(shell)

    assert "172.17.0.0/16" in cidrs
    assert "172.18.0.0/16" in cidrs
    assert "172.19.0.0/16" in cidrs
    # eth1 is not a docker bridge.
    assert "10.0.0.0/24" not in cidrs
