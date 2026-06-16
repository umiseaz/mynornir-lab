"""
diff.py — Config diff tool for MPLS L3VPN lab

Type 1 — Local diff:  compare rendered/ vs git HEAD
Type 2 — Device diff: compare rendered/ vs device running-config

Usage:
    python3 diff.py --local                    # git diff all rendered configs
    python3 diff.py --local --host pe1         # git diff specific host
    python3 diff.py --device                   # rendered vs running-config all hosts
    python3 diff.py --device --host pe1 pe2    # rendered vs running-config specific hosts
    python3 diff.py --device --save            # save diff to logs/

Exit codes:
    0 — no differences found
    1 — differences found
"""

import os
import sys
import argparse
import datetime
import difflib
import subprocess
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command

# ── Color codes ──────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Lines to strip from running-config before diffing ────────
# These are IOS auto-generated lines not in our rendered configs
STRIP_PATTERNS = [
    "Building configuration",
    "Current configuration",
    "version 15",
    "version 16",
    "version 17",
    "service timestamps",
    "service password-encryption",
    "no service password-encryption",
    "boot-start-marker",
    "boot-end-marker",
    "no aaa new-model",
    "aaa new-model",
    "bsd-client",
    "clock timezone",
    "mmi polling",
    "no mmi",
    "mmi snmp",
    "cts logging",
    "redundancy",
    "ip cef",
    "no ipv6 cef",
    "ipv6 cef",
    "multilink bundle-name",
    "no ip domain lookup",
    "spanning-tree",
    "! Last configuration",
    "! NVRAM config",
]

# ── Interface patterns to skip — unused IOU interfaces ───────
SKIP_INTERFACE_PATTERNS = [
    "Serial",
    "Ethernet0/1",
    "Ethernet0/2",
    "Ethernet0/3",
    "Ethernet1/1",
    "Ethernet1/2",
]

# ── Print helpers ─────────────────────────────────────────────
def print_header(text):
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN} {text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")

def print_ok(msg):
    print(f"  {GREEN}[=]{RESET} {msg}")

def print_diff_add(line):
    print(f"{GREEN}+ {line}{RESET}")

def print_diff_remove(line):
    print(f"{RED}- {line}{RESET}")

def print_diff_context(line):
    print(f"  {line}")

# ── Clean running-config ──────────────────────────────────────
def clean_running_config(raw):
    """Strip IOS noise lines from running-config."""
    lines = raw.splitlines()
    cleaned = []
    skip_block = False

    for line in lines:
        # Skip noise patterns
        if any(pattern in line for pattern in STRIP_PATTERNS):
            continue

        # Skip unused interface blocks
        if line.startswith("interface"):
            skip_block = any(p in line for p in SKIP_INTERFACE_PATTERNS)

        if skip_block:
            # Skip until next section
            if line.startswith("interface") or (line == "!" and skip_block):
                if line == "!":
                    skip_block = False
                continue

        # Skip lines with only !
        # Keep meaningful content
        cleaned.append(line.rstrip())

    # Remove consecutive blank lines
    result = []
    prev_empty = False
    for line in cleaned:
        if line.strip() == "" or line.strip() == "!":
            if not prev_empty:
                result.append(line)
            prev_empty = True
        else:
            prev_empty = False
            result.append(line)

    return "\n".join(result)

# ── Clean rendered config ─────────────────────────────────────
def clean_rendered_config(raw):
    """Normalize rendered config for comparison."""
    lines = raw.splitlines()
    cleaned = []
    for line in lines:
        cleaned.append(line.rstrip())
    return "\n".join(cleaned)

# ── Type 1 — Local git diff ───────────────────────────────────
def local_diff(hosts=None):
    """Show git diff of rendered configs."""
    print_header("Local Diff — rendered/ vs git HEAD")

    rendered_dir = os.path.join(BASE_DIR, "rendered")
    has_diff = False

    if hosts:
        files = [os.path.join(rendered_dir, f"{h.lower()}.cfg") for h in hosts]
    else:
        files = sorted([
            os.path.join(rendered_dir, f)
            for f in os.listdir(rendered_dir)
            if f.endswith(".cfg")
        ])

    for cfg_file in files:
        hostname = os.path.basename(cfg_file).replace(".cfg", "").upper()

        try:
            result = subprocess.run(
                ["git", "diff", cfg_file],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
            )
            diff_output = result.stdout

            if diff_output:
                has_diff = True
                print(f"\n{BOLD}── {hostname} ──{RESET}")
                for line in diff_output.splitlines():
                    if line.startswith("+") and not line.startswith("+++"):
                        print(f"{GREEN}{line}{RESET}")
                    elif line.startswith("-") and not line.startswith("---"):
                        print(f"{RED}{line}{RESET}")
                    elif line.startswith("@@"):
                        print(f"{CYAN}{line}{RESET}")
                    else:
                        print(line)
            else:
                print_ok(f"{hostname} — no changes")

        except Exception as e:
            print(f"{RED}[!] Error diffing {hostname}: {e}{RESET}")

    if not has_diff:
        print(f"\n{GREEN}All rendered configs match git HEAD — no local changes.{RESET}")

    return has_diff

# ── Nornir task — get running config ─────────────────────────
def get_running_config(task):
    """Fetch running-config from device."""
    result = task.run(
        task=netmiko_send_command,
        command_string="show running-config",
        use_textfsm=False,
    )
    return result.result

# ── Type 2 — Device diff ──────────────────────────────────────
def device_diff(nr, hosts=None, save=False):
    """Compare rendered configs against device running-config."""
    print_header("Device Diff — rendered/ vs running-config")

    has_diff = False
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = os.path.join(BASE_DIR, f"logs/{timestamp}_diff")

    if save:
        os.makedirs(log_dir, exist_ok=True)

    # Filter hosts
    if hosts:
        nr_filtered = nr.filter(
            filter_func=lambda h: h.name.lower() in [x.lower() for x in hosts]
        )
    else:
        nr_filtered = nr

    diff_summary = []

    for host_name in nr_filtered.inventory.hosts:
        rendered_file = os.path.join(BASE_DIR, f"rendered/{host_name.lower()}.cfg")

        if not os.path.exists(rendered_file):
            print(f"{YELLOW}[!] {host_name} — no rendered config found, skipping{RESET}")
            continue

        print(f"\n{BOLD}── {host_name} ──{RESET}")

        # Get running config from device
        try:
            nr_host = nr_filtered.filter(name=host_name)
            result = nr_host.run(task=get_running_config)
            running_raw = result[host_name][0].result
        except Exception as e:
            print(f"{RED}[✗] Failed to connect: {e}{RESET}")
            diff_summary.append(f"[FAIL] {host_name} — connection error")
            continue

        # Clean both configs
        running_clean = clean_running_config(running_raw)
        with open(rendered_file) as f:
            rendered_raw = f.read()
        rendered_clean = clean_rendered_config(rendered_raw)

        # Generate unified diff
        running_lines  = running_clean.splitlines(keepends=True)
        rendered_lines = rendered_clean.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            running_lines,
            rendered_lines,
            fromfile=f"{host_name} (running-config)",
            tofile=f"{host_name} (rendered)",
            lineterm="",
        ))

        if diff:
            has_diff = True
            diff_summary.append(f"[DIFF] {host_name} — {len(diff)} lines differ")
            print(f"{YELLOW}  Differences found:{RESET}")
            for line in diff:
                line = line.rstrip()
                if line.startswith("+") and not line.startswith("+++"):
                    print(f"{GREEN}  {line}{RESET}")
                elif line.startswith("-") and not line.startswith("---"):
                    print(f"{RED}  {line}{RESET}")
                elif line.startswith("@@"):
                    print(f"{CYAN}  {line}{RESET}")

            if save:
                diff_file = os.path.join(log_dir, f"{host_name.lower()}_diff.txt")
                with open(diff_file, "w") as f:
                    f.writelines(diff)
        else:
            print_ok(f"No differences — running-config matches rendered")
            diff_summary.append(f"[ OK ] {host_name}")

    # Summary
    print_header("Diff Summary")
    for line in diff_summary:
        if "DIFF" in line:
            print(f"{YELLOW}{line}{RESET}")
        elif "FAIL" in line:
            print(f"{RED}{line}{RESET}")
        else:
            print(f"{GREEN}{line}{RESET}")

    if save and has_diff:
        print(f"\n{CYAN}Diffs saved to: logs/{timestamp}_diff/{RESET}")

    return has_diff

# ── Main ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="MPLS L3VPN Lab — Config Diff Tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--local",  action="store_true", help="Git diff rendered/ vs HEAD")
    group.add_argument("--device", action="store_true", help="Diff rendered/ vs running-config")
    parser.add_argument("--host",  nargs="+", help="Specific host(s)")
    parser.add_argument("--save",  action="store_true", help="Save device diff to logs/")
    args = parser.parse_args()

    if args.local:
        has_diff = local_diff(hosts=args.host)
        sys.exit(1 if has_diff else 0)

    if args.device:
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
        has_diff = device_diff(nr, hosts=args.host, save=args.save)
        sys.exit(1 if has_diff else 0)


if __name__ == "__main__":
    main()