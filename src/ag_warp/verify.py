"""End-to-end verification of the ag-warp routing chain."""

from __future__ import annotations

from dataclasses import dataclass

from ag_warp.config import AppConfig
from ag_warp.shell import Shell, console


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def run_verify(config: AppConfig, shell: Shell) -> list[CheckResult]:
    """Execute all verification checks. Returns a list of results."""
    gid = _resolve_gid(config.group_name, shell)
    results: list[CheckResult] = []

    results.append(_check_warp_proxy(config, shell))
    results.append(_check_singbox_listening(config, shell))
    results.append(_check_nft_table(config, shell))

    if gid is not None:
        results.append(_check_warp_routing(gid, shell))
        results.append(_check_direct_routing(shell))
        results.append(_check_process_group(config, shell))
    else:
        results.append(CheckResult("GID resolve", False, f"group {config.group_name} not found"))

    results.append(_check_cloudflared(shell))

    return results


def print_results(results: list[CheckResult]) -> bool:
    """Print verification results. Returns ``True`` if all passed."""
    all_ok = True
    for r in results:
        icon = "[green]✓[/green]" if r.ok else "[red]✗[/red]"
        detail = f" — {r.detail}" if r.detail else ""
        console.print(f"  {icon} {r.name}{detail}")
        if not r.ok:
            all_ok = False
    return all_ok


# -- individual checks --------------------------------------------------------


def _resolve_gid(group_name: str, shell: Shell) -> int | None:
    r = shell.run_read(["getent", "group", group_name])
    if r.returncode != 0:
        return None
    parts = r.stdout.strip().split(":")
    return int(parts[2]) if len(parts) >= 3 else None


def _check_warp_proxy(config: AppConfig, shell: Shell) -> CheckResult:
    host, port = config.warp.proxy_host, config.warp.proxy_port
    r = shell.run_read(["ss", "-ltnp"])
    listening = f":{port}" in r.stdout if r.returncode == 0 else False
    return CheckResult(
        f"WARP proxy {host}:{port}",
        listening,
        "listening" if listening else "not listening",
    )


def _check_singbox_listening(config: AppConfig, shell: Shell) -> CheckResult:
    host, port = config.singbox.listen_host, config.singbox.listen_port
    r = shell.run_read(["ss", "-ltnp"])
    listening = f":{port}" in r.stdout if r.returncode == 0 else False
    return CheckResult(
        f"sing-box {host}:{port}",
        listening,
        "listening" if listening else "not listening",
    )


def _check_nft_table(config: AppConfig, shell: Shell) -> CheckResult:
    r = shell.run_read(
        [
            "nft",
            "list",
            "table",
            config.nftables.table_family,
            config.nftables.table_name,
        ]
    )
    exists = r.returncode == 0
    return CheckResult(
        f"nftables {config.nftables.table_family} {config.nftables.table_name}",
        exists,
        "present" if exists else "missing",
    )


def _check_warp_routing(gid: int, shell: Shell) -> CheckResult:
    r = shell.run_read(
        [
            "setpriv",
            f"--regid={gid}",
            "--clear-groups",
            "curl",
            "-sf",
            "-m5",
            "-4",
            "https://www.cloudflare.com/cdn-cgi/trace",
        ]
    )
    warp_on = "warp=on" in r.stdout if r.returncode == 0 else False
    return CheckResult(
        "GID traffic → WARP",
        warp_on,
        "warp=on" if warp_on else "warp≠on or curl failed",
    )


def _check_direct_routing(shell: Shell) -> CheckResult:
    r = shell.run_read(
        [
            "curl",
            "-sf",
            "-m5",
            "-4",
            "https://www.cloudflare.com/cdn-cgi/trace",
        ]
    )
    warp_off = "warp=off" in r.stdout if r.returncode == 0 else False
    return CheckResult(
        "Normal traffic → direct",
        warp_off,
        "warp=off" if warp_off else "warp≠off (may indicate full-host WARP)",
    )


def _check_process_group(config: AppConfig, shell: Shell) -> CheckResult:
    r = shell.run_read(["ps", "-eo", "pid,group,args"])
    if r.returncode != 0:
        return CheckResult("Antigravity process group", False, "ps failed")

    ag_procs = [
        line
        for line in r.stdout.splitlines()
        if "language_server" in line or "extensionHost" in line
    ]

    if not ag_procs:
        return CheckResult(
            "Antigravity process group",
            True,
            "no running Antigravity processes found",
        )

    in_group = all(config.group_name in line for line in ag_procs)
    return CheckResult(
        "Antigravity process group",
        in_group,
        f"{config.group_name}" if in_group else "some processes NOT in group",
    )


def _check_cloudflared(shell: Shell) -> CheckResult:
    if not shell.has_command("cloudflared"):
        return CheckResult("cloudflared", True, "not installed (OK)")

    r = shell.run_read(["pgrep", "-x", "cloudflared"])
    running = r.returncode == 0
    return CheckResult(
        "cloudflared",
        running,
        "running" if running else "not running",
    )
