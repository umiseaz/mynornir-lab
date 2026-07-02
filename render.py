import os
import sys
import yaml
import glob
from jinja2 import Environment, FileSystemLoader, StrictUndefined

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

    if not isinstance(host_data, dict) or "hostname" not in host_data:
        print(f"[!] {rel}: missing required key 'hostname'")
        failed.append(rel)
        continue

    data = {**defaults, **host_data}
    hostname = data["hostname"]

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