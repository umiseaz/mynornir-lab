"""
collect.py — Nornir show command collector for MPLS L3VPN lab

Usage:
    python3 collect.py --task ospf
    python3 collect.py --task bgp
    python3 collect.py --task all
    python3 collect.py --task ospf --host pe1
    python3 collect.py --task all --group core
    python3 collect.py --task vrf --host pe1 pe2

Exit codes:
    0 — all commands collected successfully
    1 — one or more routers failed
"""

import os
import sys
import argparse
import datetime
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from nornir.core.filter import F

# ── Color codes ──────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Task definitions ─────────────────────────────────────────
# Role-based commands — only run on routers where they make sense
TASKS = {
    "ospf": {
        "commands": [
            "show ip ospf neighbor",
            "show ip ospf interface brief",
        ],
        "roles": ["pe", "p", "rr"],
    },
    "ldp": {
        "commands": [
            "show mpls ldp neighbor",
            "show mpls ldp bindings",
            "show mpls interface",
        ],
        "roles": ["pe", "p", "rr"],
    },
    "bgp": {
        "commands": [
            "show ip bgp summary", 
            "show bgp vpnv4 unicast all summary",
            "show bgp vpnv4 unicast all",
        ],
        "roles": ["pe", "p", "rr"],
    },
    "vrf": {
        "commands": [
            "show ip route vrf VRF_A",
            "show ip bgp vpnv4 vrf VRF_A",
        ],
        "roles": ["pe"],
    },
    "mpls": {
        "commands": [
            "show mpls forwarding-table",
        ],
        "roles": ["pe", "p", "rr"],
    },
    "ce": {
        "commands": [
            "show ip route",
            "show ip bgp summary",
            "show ip bgp",
            "ping 88.88.88.88 source Loopback0 repeat 5",
            "ping 172.1.48.8 source Loopback0 repeat 5", 
        ],
        "roles": ["ce"],
    },
    "all": {
        "commands": [
            "show ip ospf neighbor",
            "show mpls ldp neighbor",
            "show bgp vpnv4 unicast all summary",
            "show ip route vrf VRF_A",
            "show mpls forwarding-table",
        ],
        "roles": ["pe", "p", "rr"],
    },
}

# ── Logging setup ─────────────────────────────────────────────
def setup_log_dir():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = os.path.join(BASE_DIR, f"logs/{timestamp}")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir, timestamp

# ── Print helpers ─────────────────────────────────────────────
def print_header(text):
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN} {text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")

def print_ok(host, msg):
    print(f"{GREEN}[✓]{RESET} {BOLD}{host}{RESET} — {msg}")

def print_fail(host, msg):
    print(f"{RED}[✗]{RESET} {BOLD}{host}{RESET} — {msg}")

def print_info(host, msg):
    print(f"{YELLOW}[!]{RESET} {BOLD}{host}{RESET} — {msg}")

# ── Nornir task ───────────────────────────────────────────────
def run_show_commands(task, commands, log_dir):
    """Run a list of show commands on a host and save output."""
    host = task.host.name
    role = task.host.data.get("role", "unknown")
    output_lines = []
    failed = False

    output_lines.append(f"Host    : {host}")
    output_lines.append(f"Role    : {role}")
    output_lines.append(f"IP      : {task.host.hostname}")
    output_lines.append(f"Time    : {datetime.datetime.now()}")
    output_lines.append("=" * 60)

    for cmd in commands:
        output_lines.append(f"\n>>> {cmd}")
        output_lines.append("-" * 60)
        try:
            result = task.run(
                task=netmiko_send_command,
                command_string=cmd,
                use_textfsm=False,
            )
            output_lines.append(result.result)
            print_ok(host, cmd)
        except Exception as e:
            output_lines.append(f"ERROR: {e}")
            print_fail(host, f"{cmd} — {e}")
            failed = True

    # Save per-host log
    log_file = os.path.join(log_dir, f"{host.lower()}.log")
    with open(log_file, "w") as f:
        f.write("\n".join(output_lines))

    return failed

# ── Main ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="MPLS L3VPN Lab — Show Command Collector")
    parser.add_argument("--task",  required=True, choices=list(TASKS.keys()), help="Task to run")
    parser.add_argument("--host",  nargs="+", help="Specific host(s) to target")
    parser.add_argument("--group", help="Target a Nornir group (core/ce)")
    args = parser.parse_args()

    # ── Init Nornir ──
    nr = InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": 5}},
        inventory={
            "plugin": "SimpleInventory",
            "options": {
                "host_file":     os.path.join(BASE_DIR, "inventory/hosts.yaml"),
                "group_file":    os.path.join(BASE_DIR, "inventory/groups.yaml"),
                "defaults_file": os.path.join(BASE_DIR, "inventory/defaults.yaml"),
            },
        },
    )

    # ── Filter hosts ──
    task_def = TASKS[args.task]
    commands = task_def["commands"]
    allowed_roles = task_def["roles"]

    if args.host:
        # Specific hosts requested
        nr_filtered = nr.filter(filter_func=lambda h: h.name.lower() in [x.lower() for x in args.host])
    elif args.group:
        # Group filter
        nr_filtered = nr.filter(F(groups__contains=args.group))
    else:
        # Filter by role from host data
        nr_filtered = nr.filter(filter_func=lambda h: h.data.get("role") in allowed_roles)

    if not nr_filtered.inventory.hosts:
        print(f"{RED}[!] No hosts matched the filter.{RESET}")
        sys.exit(1)

    # ── Setup logging ──
    log_dir, timestamp = setup_log_dir()
    print_header(f"Task: {args.task.upper()} | Hosts: {len(nr_filtered.inventory.hosts)} | Log: logs/{timestamp}")

    # ── Run tasks ──
    failed_hosts = []
    summary_lines = []

    for host_name in nr_filtered.inventory.hosts:
        host = nr_filtered.inventory.hosts[host_name]
        role = host.data.get("role", "unknown")

        # Skip if role not in allowed roles for this task
        if role not in allowed_roles and not args.host:
            print_info(host_name, f"skipped — role '{role}' not applicable for task '{args.task}'")
            continue

        print(f"\n{BOLD}── {host_name} ({role}) ──{RESET}")

        nr_host = nr_filtered.filter(name=host_name)
        result = nr_host.run(
            task=run_show_commands,
            commands=commands,
            log_dir=log_dir,
        )

        if result[host_name].failed:
            failed_hosts.append(host_name)
            summary_lines.append(f"[FAIL] {host_name}")
        else:
            summary_lines.append(f"[ OK ] {host_name}")

    # ── Summary ──
    print_header("Summary")
    for line in summary_lines:
        if "FAIL" in line:
            print(f"{RED}{line}{RESET}")
        else:
            print(f"{GREEN}{line}{RESET}")

    # Save summary log
    summary_file = os.path.join(log_dir, "summary.log")
    with open(summary_file, "w") as f:
        f.write(f"Task    : {args.task}\n")
        f.write(f"Time    : {timestamp}\n")
        f.write(f"Hosts   : {len(summary_lines)}\n")
        f.write(f"Failed  : {len(failed_hosts)}\n")
        f.write("=" * 60 + "\n")
        f.write("\n".join(summary_lines))

    print(f"\n{CYAN}Logs saved to: logs/{timestamp}/{RESET}")

    # ── Exit code ──
    sys.exit(1 if failed_hosts else 0)


if __name__ == "__main__":
    main()