import os
import sys
import glob
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_config
from nornir_utils.plugins.functions import print_result

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Confirmation gate — must pass --yes to actually push ──
if "--yes" not in sys.argv:
    print("This will push rendered/*.cfg to all devices.")
    print("Recommended flow:")
    print("    python3 render.py")
    print("    python3 healthcheck.py        # confirm healthy BEFORE")
    print("    python3 deploy.py --yes       # push")
    print("    python3 healthcheck.py        # confirm healthy AFTER")
    print()
    print("Run again with --yes to confirm, e.g.:")
    print("    python3 deploy.py --yes")
    print("    python3 deploy.py --yes --limit PE2")
    sys.exit(0)

# ── Optional --limit HOSTNAME ──────────────────────────────
limit_host = None
if "--limit" in sys.argv:
    limit_host = sys.argv[sys.argv.index("--limit") + 1]

# ── Nornir inventory ───────────────────────────────────────
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

if limit_host:
    nr = nr.filter(name=limit_host)
    if not nr.inventory.hosts:
        print(f"[!] No host matched '{limit_host}'")
        sys.exit(1)

# ── Load rendered configs from disk only — no templating here ──
rendered_configs = {}
for cfg_file in glob.glob(os.path.join(BASE_DIR, "rendered/*.cfg")):
    hostname_lower = os.path.basename(cfg_file).replace(".cfg", "")
    with open(cfg_file) as f:
        rendered_configs[hostname_lower] = f.read()

# ── Push task ───────────────────────────────────────────────
def push_config(task):
    hostname_lower = task.host.name.lower()
    config = rendered_configs.get(hostname_lower)

    if not config:
        print(f"[!] No rendered config found for {task.host.name} — run render.py first")
        return

    config_lines = [
        line for line in config.splitlines()
        if line.strip() and not line.strip().startswith("!")
    ]

    print(f"[~] Pushing config to {task.host.name}...")
    task.run(
        task=netmiko_send_config,
        config_commands=config_lines,
    )
    print(f"[✓] {task.host.name} done")

print("Pushing configs to devices...")
results = nr.run(task=push_config)
print_result(results)