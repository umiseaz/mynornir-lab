import os
import yaml
import glob
from nornir import InitNornir
from nornir_utils.plugins.functions import print_result
from jinja2 import Environment, FileSystemLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Nornir inventory
nr = InitNornir(
    runner={
        "plugin": "threaded",
        "options": {"num_workers": 5}
    },
    inventory={
        "plugin": "SimpleInventory",
        "options": {
            "host_file": os.path.join(BASE_DIR, "inventory/hosts.yaml"),
            "group_file": os.path.join(BASE_DIR, "inventory/groups.yaml"),
            "defaults_file": os.path.join(BASE_DIR, "inventory/defaults.yaml"),
        }
    }
)

# Jinja2 environment
env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates/")),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Render master.j2 for every host
host_files = sorted(glob.glob(os.path.join(BASE_DIR, "host_vars/*.yaml")))

for host_file in host_files:
    with open(host_file) as f:
        data = yaml.safe_load(f)

    hostname = data["hostname"]
    template = env.get_template("master.j2")
    rendered = template.render(**data)

    out_path = os.path.join(BASE_DIR, f"rendered/{hostname.lower()}.cfg")
    with open(out_path, "w") as f:
        f.write(rendered)

    print(f"[+] {hostname} -> rendered/{hostname.lower()}.cfg")