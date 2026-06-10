# MPLS L3VPN Lab Automation

A complete network automation framework for a Cisco IOS MPLS L3VPN lab built with Nornir, Jinja2, Netmiko, and TextFSM.

---

## Lab Topology

```
AS65 — OSPF65 / MPLS LDP / iBGP with Route Reflectors
                                                        
         RR1 (5.5.5.5)          RR2 (6.6.6.6)         
              |                       |                  
         P1 (2.2.2.2) ─────── P2 (3.3.3.3)            
              |                       |                  
         PE1 (1.1.1.1)          PE2 (4.4.4.4)          
              |                       |                  
         CE1 (77.77.77.77)      CE2 (88.88.88.88)       
                    AS65001                              
```

| Device | IOU | Role | Loopback | OOB |
|--------|-----|------|----------|-----|
| PE1 | IOU1 | PE | 1.1.1.1 | 10.1.1.1 |
| P1  | IOU2 | P  | 2.2.2.2 | 10.1.1.2 |
| P2  | IOU3 | P  | 3.3.3.3 | 10.1.1.3 |
| PE2 | IOU4 | PE | 4.4.4.4 | 10.1.1.4 |
| RR1 | IOU5 | RR | 5.5.5.5 | 10.1.1.5 |
| RR2 | IOU6 | RR | 6.6.6.6 | 10.1.1.6 |
| CE1 | IOU7 | CE | 77.77.77.77 | 10.1.1.7 |
| CE2 | IOU8 | CE | 88.88.88.88 | 10.1.1.8 |

**P2P Links:**

| Link | Subnet |
|------|--------|
| PE1 ↔ P1 | 10.1.2.0/24 |
| P1 ↔ P2 | 10.2.3.0/24 |
| P1 ↔ RR1 | 10.2.5.0/24 |
| P2 ↔ RR2 | 10.3.6.0/24 |
| P2 ↔ PE2 | 10.3.4.0/24 |
| PE1 ↔ CE1 | 172.1.17.0/24 (VRF A) |
| PE2 ↔ CE2 | 172.1.48.0/24 (VRF A) |

---

## Project Structure

```
mynornir-lab/
  templates/             Jinja2 config templates
    base.j2              hostname, SSH, mgmt VRF, NTP, syslog
    vrf.j2               VRF definition (PE only)
    interfaces.j2        all interfaces, OSPF, MPLS per interface
    ospf.j2              OSPF process block
    mpls.j2              MPLS LDP
    bgp.j2               BGP process, peer-session, peer-policy, iBGP
    bgp_vpnv4.j2         address-family vpnv4
    bgp_pe_ce.j2         address-family ipv4 vrf (PE only)
    bgp_ce.j2            CE eBGP (CE only)
    prefix_lists.j2      prefix-lists
    route_maps.j2        route-maps
    master.j2            role-based template orchestration

  host_vars/             per-device YAML data
    pe1.yaml pe2.yaml
    p1.yaml  p2.yaml
    rr1.yaml rr2.yaml
    ce1.yaml ce2.yaml

  inventory/             Nornir inventory
    hosts.yaml           device IPs and group membership
    groups.yaml          group-level settings (platform, device_type)
    defaults.yaml        shared defaults (NTP, syslog, OSPF auth)

  textfsm/               custom TextFSM templates
    cisco_ios_show_mpls_ldp_neighbor.textfsm
    cisco_ios_show_bgp_vpnv4_unicast_all_summary.textfsm

  rendered/              generated device configs (output)
  bootstrap/             minimal bootstrap configs for OOB bring-up
  logs/                  timestamped show command logs
  baseline.json          healthy state snapshot for health checks

  render.py              render all 8 configs from templates + YAML
  test_template.py       test individual templates against specific hosts
  collect.py             collect show commands, save timestamped logs
  healthcheck.py         baseline capture + health check with alerts
  save.py                push rendered configs to devices via Netmiko
```

---

## Scripts

### render.py
Renders all 8 device configs from Jinja2 templates and host_vars YAML.

```bash
python3 render.py
```

### test_template.py
Test a single template against one or more hosts without full render.

```bash
python3 test_template.py bgp.j2 pe1
python3 test_template.py interfaces.j2 pe1 pe2 p1
python3 test_template.py ospf.j2 rr1 rr2
```

### collect.py
Run show commands across devices, save timestamped logs per host.

```bash
python3 collect.py --task ospf               # OSPF on all core routers
python3 collect.py --task bgp                # BGP on all core routers
python3 collect.py --task ldp                # LDP on all core routers
python3 collect.py --task vrf                # VRF routing on PE only
python3 collect.py --task mpls               # MPLS on all core routers
python3 collect.py --task ce                 # CE routing + ping
python3 collect.py --task all                # everything
python3 collect.py --task ospf --host pe1    # specific host
python3 collect.py --task bgp --group core   # specific group
```

### healthcheck.py
Capture baseline state and compare future state against it.

```bash
python3 healthcheck.py --baseline            # capture healthy state
python3 healthcheck.py                       # compare vs baseline
python3 healthcheck.py --host pe1 p1         # check specific hosts
```

Exit codes: `0` all OK, `1` one or more failures.

---

## Key Design Decisions

### Jinja2 — keep templates dumb
All logic lives in YAML. Templates only loop and substitute.

```
YAML  → decisions (what exists, what's enabled)
Jinja → rendering (loop, substitute, include)
```

### Role-based template inclusion
`master.j2` includes templates based on device role:

| Template | PE | P | RR | CE |
|----------|-----|---|----|----|
| base.j2 | ✅ | ✅ | ✅ | ✅ |
| vrf.j2 | ✅ | ❌ | ❌ | ❌ |
| ospf.j2 | ✅ | ✅ | ✅ | ❌ |
| mpls.j2 | ✅ | ✅ | ✅ | ❌ |
| bgp.j2 | ✅ | ✅ | ✅ | ❌ |
| bgp_vpnv4.j2 | ✅ | ❌ | ✅ | ❌ |
| bgp_pe_ce.j2 | ✅ | ❌ | ❌ | ❌ |
| bgp_ce.j2 | ❌ | ❌ | ❌ | ✅ |

### defaults.yaml — one place for shared config
NTP, syslog, OSPF auth key defined once, applied to all routers via merge.

### Baseline health checks
Captures healthy state as JSON. Any deviation from baseline triggers alert
with full cascade impact visible across all routers.

---

## Features Implemented

- OSPF MD5 authentication on all P2P interfaces
- MPLS LDP with loopback router-id
- BGP peer-session + peer-policy templates (real ISP style)
- Route reflector design — RR1/RR2 with edge/core/rr-other sessions
- VPNv4 L3VPN — VRF A, RD/RT 65:65001
- PE-CE eBGP with as-override
- Prefix-lists and route-maps on PE and CE
- NTP and syslog from defaults
- Parallel execution via Nornir threaded runner
- Color coded terminal output
- Timestamped log files per run
- Exit codes for automation pipelines

---

## Dependencies

```bash
pip install nornir nornir-netmiko nornir-utils
pip install nornir-jinja2
pip install textfsm ntc-templates
pip install pyyaml
```

---

## What Was Verified

All configs deployed to GNS3 IOU lab and verified:

- OSPF adjacencies — all FULL, cost 10 on IOU links
- MPLS LDP — all sessions Oper
- iBGP — all peers Established via RR1/RR2
- VPNv4 — prefixes exchanged correctly
- CE1 ping CE2 loopback — 100% success
- Health check failure detection — cascade impact visible on single link failure
- Health check recovery — all green after interface restore