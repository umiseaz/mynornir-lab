import os
import sys
import yaml
import glob
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from secrets_resolver import resolve_deep

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

# ── Jinja2 environment ────────────────────────────────────
# StrictUndefined: a missing/typo'd YAML key fails the render loudly
# instead of silently producing an empty value in the config.
env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates/")),
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)

# ── Load defaults ─────────────────────────────────────────
with open(os.path.join(BASE_DIR, "inventory/defaults.yaml")) as f:
    defaults = yaml.safe_load(f) or {}

# ── Load inventory hosts (role is sourced from here) ───────
with open(os.path.join(BASE_DIR, "inventory/hosts.yaml")) as f:
    inventory_hosts = yaml.safe_load(f) or {}

# rendered/ is gitignored (contains real secrets once rendered) and won't
# exist on a fresh checkout — create it if missing rather than assuming.
os.makedirs(os.path.join(BASE_DIR, "rendered"), exist_ok=True)

# ── Render only — no SSH, no device contact at all ────────
host_files = sorted(glob.glob(os.path.join(BASE_DIR, "host_vars/*.yaml")))

failed = []

for host_file in host_files:
    rel = os.path.relpath(host_file, BASE_DIR)

    try:
        with open(host_file) as f:
            host_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"[!] {rel}: invalid YAML — {e}")
        failed.append(rel)
        continue

    if not isinstance(host_data, dict) or "device_name" not in host_data:
        print(f"[!] {rel}: missing required key 'device_name'")
        failed.append(rel)
        continue

    data = resolve_deep({**defaults, **host_data})
    hostname = data["device_name"]

    role = inventory_hosts.get(hostname, {}).get("data", {}).get("role")
    if role is not None:
        data["role"] = role

    try:
        rendered = env.get_template("master.j2").render(**data)
    except Exception as e:
        print(f"[!] {rel}: render failed — {e}")
        failed.append(rel)
        continue

    out_path = os.path.join(BASE_DIR, f"rendered/{hostname.lower()}.cfg")
    with open(out_path, "w") as f:
        f.write(rendered)

    print(f"[+] {hostname} -> rendered/{hostname.lower()}.cfg")

if failed:
    print(f"\nRender FAILED for {len(failed)} host_vars file(s): {', '.join(failed)}")
    sys.exit(1)

print("\nRender complete. Review rendered/*.cfg before running deploy.py.")