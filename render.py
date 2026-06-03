import os
import sys
import yaml
import glob
from nornir import InitNornir
from nornir_utils.plugins.functions import print_result
from nornir_netmiko.tasks import netmiko_send_config
from jinja2 import Environment, FileSystemLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Dry run flag ──────────────────────────────────────────
DRY_RUN = "--dry-run" in sys.argv

# ── Nornir inventory ──────────────────────────────────────
nr = InitNornir(
    runner={"plugin": "threaded", "options": {"num_workers": 5}},
    inventory={
        "plugin": "SimpleInventory",
        "options": {
            "host_file": os.path.join(BASE_DIR, "inventory/hosts.yaml"),
            "group_file": os.path.join(BASE_DIR, "inventory/groups.yaml"),
            "defaults_file": os.path.join(BASE_DIR, "inventory/defaults.yaml"),
        }
    }
)

# ── Jinja2 environment ────────────────────────────────────
env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates/")),
    trim_blocks=True,
    lstrip_blocks=True,
)

# ── Load defaults ─────────────────────────────────────────
with open(os.path.join(BASE_DIR, "inventory/defaults.yaml")) as f:
    defaults = yaml.safe_load(f) or {}

# ── Render ────────────────────────────────────────────────
rendered_configs = {}
host_files = sorted(glob.glob(os.path.join(BASE_DIR, "host_vars/*.yaml")))

for host_file in host_files:
    with open(host_file) as f:
        host_data = yaml.safe_load(f)

    data = {**defaults, **host_data}
    hostname = data["hostname"]
    rendered = env.get_template("master.j2").render(**data)

    out_path = os.path.join(BASE_DIR, f"rendered/{hostname.lower()}.cfg")
    with open(out_path, "w") as f:
        f.write(rendered)

    rendered_configs[hostname] = rendered
    print(f"[+] {hostname} -> rendered/{hostname.lower()}.cfg")

# ── Push or dry run ───────────────────────────────────────
if DRY_RUN:
    print("\n[DRY RUN] Configs rendered to rendered/ folder — no push performed.")
    print("[DRY RUN] Review configs then run without --dry-run to push.")
else:
    def push_config(task):
        hostname = task.host.name
        config = rendered_configs.get(hostname)
        if not config:
            print(f"[!] No config found for {hostname}")
            return

        config_lines = [
            line for line in config.splitlines()
            if line.strip() and not line.strip().startswith("!")
        ]

        print(f"[~] Pushing config to {hostname}...")
        task.run(
            task=netmiko_send_config,
            config_commands=config_lines,
        )
        print(f"[✓] {hostname} done")

    print("\nPushing configs to all routers...")
    results = nr.run(task=push_config)
    print_result(results)