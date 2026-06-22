# MPLS L3VPN Lab Automation
### Nornir + Jinja2 + Netmiko | IOS/IOS-XE | GNS3

---

## Project Structure

```
mynornir-lab/
  templates/          ← Jinja2 templates (one per feature)
  host_vars/          ← YAML data files (one per router)
  inventory/          ← Nornir inventory files
  rendered/           ← Generated router configs (output)
  render.py           ← Main script: render + push
  save.py             ← Save configs on all routers
  test_template.py    ← Quick template testing tool
  LAB_COMMANDS.md     ← Full command reference
```

---

## Lab Topology

| Device | IOU | Role | Loopback | OOB IP |
|---|---|---|---|---|
| PE1 | IOU1 | PE | 1.1.1.1 | 10.1.1.1 |
| P1 | IOU2 | P | 2.2.2.2 | 10.1.1.2 |
| P2 | IOU3 | P | 3.3.3.3 | 10.1.1.3 |
| PE2 | IOU4 | PE | 4.4.4.4 | 10.1.1.4 |
| RR1 | IOU5 | RR | 5.5.5.5 | 10.1.1.5 |
| RR2 | IOU6 | RR | 6.6.6.6 | 10.1.1.6 |
| CE1 | IOU7 | CE | 77.77.77.77 | 10.1.1.7 |
| CE2 | IOU8 | CE | 88.88.88.88 | 10.1.1.8 |

**AS65** — OSPF65 / MPLS LDP / iBGP with RR  
**AS65001** — CE routers, VRF A, eBGP PE-CE

---

## Templates

| Template | Applies to | What it renders |
|---|---|---|
| `base.j2` | all | hostname, SSH, mgmt VRF, NTP, syslog |
| `vrf.j2` | pe | VRF definition, RD, RT |
| `interfaces.j2` | all | interfaces, OSPF, MPLS, auth |
| `ospf.j2` | pe, p, rr | OSPF process, router-id, passive |
| `mpls.j2` | pe, p, rr | MPLS LDP |
| `bgp.j2` | pe, p, rr | BGP process, peer-session, peer-policy, iBGP |
| `bgp_vpnv4.j2` | pe, rr | address-family vpnv4 |
| `bgp_pe_ce.j2` | pe | address-family ipv4 vrf |
| `prefix_lists.j2` | pe, ce | ip prefix-list |
| `route_maps.j2` | pe, ce | route-map |
| `master.j2` | all | includes all templates, role-based |

`master.j2` controls which templates render per router role:
```jinja
{% include 'base.j2' %}
{% if role == 'pe' %}{% include 'vrf.j2' %}{% endif %}
{% include 'interfaces.j2' %}
{% if role in ['pe', 'p', 'rr'] %}
{% include 'ospf.j2' %}
{% include 'mpls.j2' %}
{% include 'bgp.j2' %}
{% include 'bgp_vpnv4.j2' %}
{% endif %}
{% if role == 'pe' %}{% include 'bgp_pe_ce.j2' %}{% endif %}
{% if prefix_lists is defined %}{% include 'prefix_lists.j2' %}{% endif %}
{% if route_maps is defined %}{% include 'route_maps.j2' %}{% endif %}
```

---

## Data Flow

```
host_vars/pe1.yaml  ──┐
inventory/defaults.yaml ─┤──► Jinja2 render ──► rendered/pe1.cfg ──► Netmiko SSH ──► PE1
                        │         ↑
host_vars/pe2.yaml  ──┘    master.j2 +
                           feature templates
```

`defaults.yaml` holds values shared across all routers (NTP, syslog, OSPF auth key).  
`host_vars/*.yaml` holds per-router data. Host values override defaults.

---

## Why Test Commands Are Safe

Test commands use only `yaml` and `jinja2` — no SSH, no network connection.

```
Test command:    YAML → Jinja2 → print to terminal   (safe, no push)
render.py:       YAML → Jinja2 → rendered/ → Netmiko SSH → router
```

| | Test commands | render.py --dry-run | render.py |
|---|---|---|---|
| Reads YAML | ✅ | ✅ | ✅ |
| Renders Jinja2 | ✅ | ✅ | ✅ |
| Saves to rendered/ | ❌ | ✅ | ✅ |
| Opens SSH | ❌ | ❌ | ✅ |
| Pushes to router | ❌ | ❌ | ✅ |

Test commands are safe to run at any time — even against production YAML — because they never touch the network.

---

## Workflow

### Adding new config (e.g. BGP advertisement)

```bash
# 1. Update host_vars YAML
vim host_vars/pe1.yaml

# 2. Validate YAML
python3 -c "import yaml; yaml.safe_load(open('host_vars/pe1.yaml')); print('OK')"

# 3. Test specific template only
python3 test_template.py bgp.j2 pe1

# 4. Dry run — render all, no push
python3 render.py --dry-run

# 5. Review rendered config
cat rendered/pe1.cfg

# 6. Push to routers
python3 render.py

# 7. Save configs
python3 save.py
```

### First time bootstrap

```bash
# Manually paste bootstrap config on each router console in GNS3
# Then verify SSH reachability
for ip in 10.1.1.1 10.1.1.2 10.1.1.3 10.1.1.4 10.1.1.5 10.1.1.6 10.1.1.7 10.1.1.8; do
    ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no admin@$ip \
        "show hostname" 2>/dev/null && echo "$ip OK" || echo "$ip FAILED"
done
```

---

## Quick Reference

```bash
# Render only (no push)
python3 render.py --dry-run

# Render + push
python3 render.py

# Save configs
python3 save.py

# Test one template for one router
python3 test_template.py bgp.j2 pe1

# Test one template for multiple routers
python3 test_template.py interfaces.j2 pe1 pe2 p1 p2 rr1 rr2

# Validate all YAML
for f in host_vars/*.yaml; do
    python3 -c "import yaml; yaml.safe_load(open('$f')); print('$f OK')"
done

# Check for config errors in rendered files
grep -n "[a-z]!" rendered/*.cfg
```

---

## Dependencies

```bash
pip install nornir nornir-netmiko nornir-utils jinja2 pyyaml --break-system-packages
```

---

## Notes

- `defaults.yaml` — shared values applied to all routers. Host vars override if same key exists.
- OSPF auth key in `defaults.yaml` under `ospf_auth` — change once, applies everywhere.
- NTP and syslog servers in `defaults.yaml` — same for all routers.
- IP addressing convention — last octet = IOU number (e.g. PE1=IOU1 → 10.1.1.1).
- BGP uses peer-session + peer-policy templates (not peer-groups).
- RR1 and RR2 are redundant route reflectors — all PE/P routers peer to both.



```
(nornir-env) khau@nuc:~/nornir-env/mynornir-lab$ python3 -c "
from nornir import InitNornir
import os
BASE_DIR = os.path.dirname(os.path.abspath('inventory/hosts.yaml'))
nr = InitNornir(inventory={'plugin': 'SimpleInventory', 'options': {'host_file': 'inventory/hosts.yaml', 'group_file': 'inventory/groups.yaml', 'defaults_file': 'inventory/defaults.yaml'}})
for host in nr.inventory.hosts:
    role = nr.inventory.hosts[host].data.get('role', 'MISSING')
    print(f'{host:6} → role: {role}')
"
PE1    → role: pe
PE2    → role: pe
P1     → role: p
P2     → role: p
RR1    → role: rr
RR2    → role: rr
CE1    → role: ce
CE2    → role: ce
```

```
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
```

```
python3 render.py && grep "auto-cost" rendered/*.cfg
```

```
healthcheck.py

ntc-templates for OSPF/BGP (lowercase keys)
Custom TextFSM for LDP/VPNv4 (uppercase keys)
Two different key naming conventions — annoying inconsistency
```