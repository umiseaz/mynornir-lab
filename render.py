import os
import yaml
import glob
from jinja2 import Environment, FileSystemLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Jinja2 environment ────────────────────────────────────
env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates/")),
    trim_blocks=True,
    lstrip_blocks=True,
)

# ── Load defaults ─────────────────────────────────────────
with open(os.path.join(BASE_DIR, "inventory/defaults.yaml")) as f:
    defaults = yaml.safe_load(f) or {}

# ── Render only — no SSH, no device contact at all ────────
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

    print(f"[+] {hostname} -> rendered/{hostname.lower()}.cfg")

print("\nRender complete. Review rendered/*.cfg before running deploy.py.")