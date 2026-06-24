# Network Automation Framework

## 🛠️ Script Reference Directory

| Script Name | Scope / Connection Type | Core Function | Safeties & Edge Cases |
| :--- | :--- | :--- | :--- |
| **`render.py`** | 🛑 Offline (No SSH) | Merges `host_vars/*.yaml` + `defaults.yaml` through `master.j2` to generate local `rendered/*.cfg` files. | None. Safe to run at any time. |
| **`deploy.py`** | ⚡ Active SSH (Netmiko) | Reads localized configuration files from `rendered/*.cfg` and pushes them live to network nodes. | Requires explicit `--yes` safety flag to run. Supports targeted staging via `--limit HOSTNAME`. |
| **`save.py`** | ⚡ Active SSH (Netmiko) | Connects to nodes and triggers a `write memory` command to commit running-config to NVRAM. | Prevents configuration loss on hardware reboots. |
| **`healthcheck.py`** | ⚡ Active SSH (Netmiko) | Collects show commands, parses them into structured data via **TextFSM**, and evaluates states against a `baseline.json`. | Generates programmatic `OK` / `FAIL` states per router. Our source of truth. |
| **`collect.py`** | ⚡ Active SSH (Netmiko) | Dumps raw, unstructured show outputs (OSPF, BGP, LDP) directly into human-readable text logs under `logs/<timestamp>/`. | No programmatic parsing or verification logic. Purely for human auditing. |
| **`test_template.py`** | 🛑 Offline (No SSH) | One-off staging utility. Renders a single test template against a single host variable file directly to `stdout`. | Ideal for rapid Jinja2 debugging without modifying production files. |

---

## 🔄 The Intended Deployment Pipeline

Execute this workflow sequentially in your terminal to ensure safe configuration changes:

```bash
# 1. Build the network configuration files locally
python3 render.py          

# 2. Confirm the network is healthy BEFORE touching anything
python3 healthcheck.py     

# 3. Push the new configuration changes live
python3 deploy.py --yes    

# 4. Confirm the network is still healthy AFTER the changes
python3 healthcheck.py     

# 5. Commit changes to NVRAM so they survive reboots
python3 save.py
```
---
```
collect.py and test_template.py are side tools you reach for when troubleshooting, not part of the regular push cycle
```
