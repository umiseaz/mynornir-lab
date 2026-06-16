#!/bin/bash
# ============================================================
# LAB TEST COMMANDS REFERENCE
# All commands run from: ~/nornir-env/mynornir-lab
# All one-liners now include defaults.yaml merge
# ============================================================

# ── HELPER FUNCTION ─────────────────────────────────────────
# Reusable Python snippet — merges defaults + host_vars
# Usage: render_template <template> <host_yaml>
render_template() {
    python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('$2'))
data = {**defaults, **host_data}
print(env.get_template('$1').render(**data))
"
}

# ── 1. VALIDATE YAML ────────────────────────────────────────

# Validate all host_vars
for f in host_vars/*.yaml; do
    python3 -c "import yaml; yaml.safe_load(open('$f')); print('$f OK')"
done

# Validate single host
python3 -c "import yaml; yaml.safe_load(open('host_vars/pe1.yaml')); print('pe1 OK')"

# Inspect specific keys in a host_vars
python3 -c "
import yaml
data = yaml.safe_load(open('host_vars/pe1.yaml'))
print('bgp router_id:', data['bgp']['router_id'])
"

# Verify defaults merge correctly
python3 -c "
import yaml
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host = yaml.safe_load(open('host_vars/pe1.yaml'))
data = {**defaults, **host}
print('ntp:', data.get('ntp'))
print('syslog:', data.get('syslog'))
print('ospf_auth:', data.get('ospf_auth'))
print('hostname:', data.get('hostname'))
"

# ── 2. TEST SINGLE TEMPLATE ─────────────────────────────────
# Uses defaults.yaml merge — safe for all templates

# base.j2
python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('host_vars/pe1.yaml'))
data = {**defaults, **host_data}
print(env.get_template('base.j2').render(**data))
"

# interfaces.j2
python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('host_vars/pe1.yaml'))
data = {**defaults, **host_data}
print(env.get_template('interfaces.j2').render(**data))
"

# ospf.j2
python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('host_vars/pe1.yaml'))
data = {**defaults, **host_data}
print(env.get_template('ospf.j2').render(**data))
"

# mpls.j2
python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('host_vars/pe1.yaml'))
data = {**defaults, **host_data}
print(env.get_template('mpls.j2').render(**data))
"

# bgp.j2
python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('host_vars/pe1.yaml'))
data = {**defaults, **host_data}
print(env.get_template('bgp.j2').render(**data))
"

# bgp_vpnv4.j2
python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('host_vars/pe1.yaml'))
data = {**defaults, **host_data}
print(env.get_template('bgp_vpnv4.j2').render(**data))
"

# bgp_pe_ce.j2
python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('host_vars/pe1.yaml'))
data = {**defaults, **host_data}
print(env.get_template('bgp_pe_ce.j2').render(**data))
"

# prefix_lists.j2
python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('host_vars/pe1.yaml'))
data = {**defaults, **host_data}
print(env.get_template('prefix_lists.j2').render(**data))
"

# route_maps.j2
python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('host_vars/pe1.yaml'))
data = {**defaults, **host_data}
print(env.get_template('route_maps.j2').render(**data))
"

# ── 3. TEST TEMPLATE ACROSS MULTIPLE HOSTS ──────────────────

# Core routers only (pe, p, rr) — any template
for f in host_vars/pe1.yaml host_vars/pe2.yaml host_vars/p1.yaml host_vars/p2.yaml host_vars/rr1.yaml host_vars/rr2.yaml; do
    echo "=== $(basename $f .yaml) ==="
    python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('$f'))
data = {**defaults, **host_data}
print(env.get_template('bgp.j2').render(**data))
"
done

# PE routers only
for f in host_vars/pe1.yaml host_vars/pe2.yaml; do
    echo "=== $(basename $f .yaml) ==="
    python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('$f'))
data = {**defaults, **host_data}
print(env.get_template('bgp_pe_ce.j2').render(**data))
"
done

# CE routers only
for f in host_vars/ce1.yaml host_vars/ce2.yaml; do
    echo "=== $(basename $f .yaml) ==="
    python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('$f'))
data = {**defaults, **host_data}
print(env.get_template('prefix_lists.j2').render(**data))
"
done

# Filter by role dynamically
for f in host_vars/*.yaml; do
    role=$(python3 -c "import yaml; print(yaml.safe_load(open('$f'))['role'])")
    if [[ "$role" != "ce" ]]; then
        echo "=== $(basename $f .yaml) ==="
        python3 -c "
import yaml
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/'), trim_blocks=True, lstrip_blocks=True)
defaults = yaml.safe_load(open('inventory/defaults.yaml')) or {}
host_data = yaml.safe_load(open('$f'))
data = {**defaults, **host_data}
print(env.get_template('mpls.j2').render(**data))
"
    fi
done

# ── 4. RENDER ALL + VERIFY ───────────────────────────────────

# Render all configs
python3 render.py

# Dry run — render only, no push
python3 render.py --dry-run

# Check for merged lines (should return empty)
grep -n "[a-z]!" rendered/*.cfg

# Count ! separators per file
for f in rendered/*.cfg; do
    echo "=== $(basename $f) ==="
    grep -c "!" $f
done

# View specific section in rendered config
grep -A10 "interface Ethernet0/0" rendered/pe1.cfg
grep -A5 "ntp\|logging" rendered/pe1.cfg
grep -A5 "router ospf" rendered/pe1.cfg
grep -A5 "router bgp" rendered/pe1.cfg

# View full rendered config
cat rendered/pe1.cfg

# View all rendered configs
for f in rendered/*.cfg; do
    echo "========== $(basename $f) =========="
    cat $f
    echo ""
done

# ── 5. VALIDATE YAML ALL 8 ───────────────────────────────────
for f in host_vars/*.yaml; do
    python3 -c "import yaml; yaml.safe_load(open('$f')); print('$f OK')"
done

# ── 6. CONNECTIVITY CHECK ────────────────────────────────────
for ip in 10.1.1.1 10.1.1.2 10.1.1.3 10.1.1.4 10.1.1.5 10.1.1.6 10.1.1.7 10.1.1.8; do
    ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no admin@$ip \
        "show hostname" 2>/dev/null && echo "$ip OK" || echo "$ip FAILED"
done

# ── 7. PUSH AND SAVE ─────────────────────────────────────────

# Push configs to all routers
python3 render.py

# Save configs on all routers
python3 save.py

# ── 8. EASIER WAY — test_template.py ────────────────────────
# python3 test_template.py <template> <host1> [host2] ...

# Test single template single host
python3 test_template.py bgp.j2 pe1

# Test single template multiple hosts
python3 test_template.py bgp.j2 pe1 pe2 rr1 rr2

# Test interfaces for all core routers
python3 test_template.py interfaces.j2 pe1 pe2 p1 p2 rr1 rr2

# Test full config for one router
python3 test_template.py master.j2 pe1

# show run
python3 -c "
import os
from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command

nr = InitNornir(
    inventory={
        'plugin': 'SimpleInventory',
        'options': {
            'host_file': 'inventory/hosts.yaml',
            'group_file': 'inventory/groups.yaml',
            'defaults_file': 'inventory/defaults.yaml',
        }
    }
)

nr_pe1 = nr.filter(name='PE1')
result = nr_pe1.run(
    task=netmiko_send_command,
    command_string='show running-config',
    use_textfsm=False,
)
print(result['PE1'][0].result[:3000])
"