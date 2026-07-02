import os
import sys
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

# Usage: python3 test_template.py bgp.j2 pe1
# Or:    python3 test_template.py bgp.j2 pe1 pe2 rr1

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

template_name = sys.argv[1]
hosts = sys.argv[2:] if len(sys.argv) > 2 else []

env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates/")),
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)

defaults = yaml.safe_load(open(os.path.join(BASE_DIR, "inventory/defaults.yaml"))) or {}

if not hosts:
    print("Usage: python3 test_template.py <template> <host1> [host2] ...")
    sys.exit(1)

for host in hosts:
    yaml_path = os.path.join(BASE_DIR, f"host_vars/{host}.yaml")
    if not os.path.exists(yaml_path):
        print(f"[!] {yaml_path} not found")
        continue
    host_data = yaml.safe_load(open(yaml_path))
    data = {**defaults, **host_data}
    print(f"=== {host} ===")
    print(env.get_template(template_name).render(**data))
    print()