"""Docker bridge network CIDR auto-discovery."""

from __future__ import annotations

import json
import re

from ag_warp.shell import Shell


def discover_docker_cidrs(shell: Shell) -> list[str]:
    """Detect Docker bridge network CIDRs.

    Strategy:
    1. Try ``docker network inspect`` (most reliable).
    2. Fallback to ``ip -4 route`` parsing for ``docker*`` / ``br-*`` devices.
    3. On failure, return empty list with a warning (never block ``on``).
    """
    cidrs = _try_docker_network_inspect(shell)
    if cidrs:
        return cidrs

    cidrs = _try_ip_route_fallback(shell)
    return cidrs


def _try_docker_network_inspect(shell: Shell) -> list[str]:
    """Extract subnet CIDRs from all Docker networks via docker CLI."""
    if not shell.has_command("docker"):
        return []

    r = shell.run_read(["docker", "network", "ls", "--format", "{{.ID}}"])
    if r.returncode != 0 or not r.stdout.strip():
        return []

    network_ids = r.stdout.strip().splitlines()
    r = shell.run_read(["docker", "network", "inspect", *network_ids])
    if r.returncode != 0:
        return []

    cidrs: list[str] = []
    try:
        networks = json.loads(r.stdout)
        for net in networks:
            ipam = net.get("IPAM") or {}
            configs = ipam.get("Config") or []
            for cfg in configs:
                if not isinstance(cfg, dict):
                    continue
                subnet = cfg.get("Subnet", "")
                if subnet and ":" not in subnet:  # IPv4 only
                    cidrs.append(subnet)
    except (AttributeError, json.JSONDecodeError, KeyError):
        return []

    return sorted(set(cidrs))


def _try_ip_route_fallback(shell: Shell) -> list[str]:
    """Parse ``ip -4 route`` for docker/bridge device routes."""
    r = shell.run_read(["ip", "-4", "route"])
    if r.returncode != 0:
        return []

    cidrs: list[str] = []
    for line in r.stdout.splitlines():
        # Match lines like: 172.17.0.0/16 dev docker0 ...
        #                    172.18.0.0/16 dev br-097001cefd20 ...
        m = re.match(r"^(\d+\.\d+\.\d+\.\d+/\d+)\s+dev\s+(docker\w*|br-\w+)", line)
        if m:
            cidrs.append(m.group(1))

    return sorted(set(cidrs))
