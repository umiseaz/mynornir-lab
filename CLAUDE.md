# CLAUDE.md

Reference for AI assistants working in this repo. For topology diagrams, the
full "why this project exists" narrative, and detailed postmortems, read
`README.md` — this file is a denser, task-oriented map: commands, data flow,
and hard constraints to respect when editing.

## What this is

Nornir + Jinja2 + Netmiko network automation for a 10-router Cisco IOS MPLS
L3VPN lab (GNS3/IOU): PE1/PE2, P1/P2, RR1/RR2, CE1-CE4, two VRFs (VRF_A,
VRF_B). Config is rendered from YAML + Jinja2 templates, validated, pushed to
devices, and verified with TextFSM-parsed health checks. Jenkins runs the
same validation on every branch/PR and deploys only on `main`.

A companion repo, `myansible-lab`, automates the *same* topology and reuses
the *same* Jinja2 templates via Ansible instead of Nornir. If you change
template output/behavior here, it's worth knowing that repo exists.

## Repository map

```
templates/*.j2          12 Jinja2 templates, role-based, included by master.j2
host_vars/*.yaml         Per-device data: interfaces, vrfs, bgp peers, prefix-lists, route-maps (10 files).
                         BGP peer-session password is "${BGP_PEER_PASSWORD}" — resolved from .env, see below.
config.yaml              Nornir config: SimpleInventory file paths + threaded runner (num_workers) +
                         transform_function: inject_credentials (resolves secrets after inventory load)
inventory/
  hosts.yaml              Nornir inventory: device IP, group, role
  groups.yaml              Group-level connection defaults (core vs ce: platform, netmiko device_type/secret).
                           secret is "${NORNIR_ENABLE_SECRET}" — resolved from .env, see below.
  defaults.yaml            Shared vars merged into every host (NTP, syslog, OSPF auth key, username/password).
                           username/password/ospf_auth.key are "${VAR}" placeholders — resolved from .env.
ci/check_vrf_consistency.py   CI gate: RD/RT must match across every PE for a given VRF name
ci/check_data_consistency.py  CI gate: reference integrity (peer-session/policy/route-map/prefix-list/VRF), duplicate IPs, router-id uniqueness, iBGP/eBGP peer resolution, inventory<->host_vars sync
rendered/*.cfg            Generated output of render.py — do not hand-edit, do not treat as source.
                          Gitignored: contains real secrets once rendered. Regenerate via render.py.
bootstrap/*.cfg           Minimal OOB bring-up configs (not touched by render.py)
useful_tips/              STALE draft notes (8-device topology, no VRF_B, pre-CI). README.md supersedes it.

secrets_resolver.py       resolve()/resolve_deep() — turns "${VAR}" placeholder strings into real values
                          read from os.environ. Shared by both secrets-resolution call sites below.
nornir_transform.py       inject_credentials(host) — the Nornir transform_function; resolves
                          username/password/enable-secret on each Host after inventory load
.env.example              Committed template listing every required env var (placeholder values only)
.env                      Gitignored, local-only, real secret values — copy from .env.example

render.py                Render-only, no SSH/device contact
deploy.py                Push-only, requires --yes, supports --limit HOST
collect.py                Ad-hoc raw show-command dumper, human-reviewed, not pass/fail. Logs to logs/<timestamp>/
save.py                   `write memory` across all devices
test_template.py          Render one template against one/more hosts, for debugging only

verification/             Everything specific to health-check verification (see below)
  healthcheck.py            Baseline capture (--baseline) + structured TextFSM-parsed health comparison
  baseline.json             Captured healthy-state snapshot — gitignored, environment-specific, regenerate don't edit
  textfsm/*.textfsm         Custom TextFSM templates: LDP neighbor + VPNv4 summary (ntc-templates doesn't cover these) and ospf_neighbor.textfsm (currently unused — OSPF is parsed via built-in ntc-templates)
  logs/*_healthcheck/       Per-run healthcheck reports

Jenkinsfile               Active CI/CD pipeline definition
old1.Jenkinsfile, old2.Jenkinsfile   Earlier pipeline iterations, kept for reference, not active
requirements.txt          Full pinned dependency set (Nornir, Netmiko, TextFSM, pyATS/Genie, etc.)
logs/<timestamp>/         collect.py's per-run raw dumps (not healthcheck — those live under verification/logs/)
nornir.log                Gitignored Nornir run log, shared across every script that calls InitNornir
```

There is no `Dockerfile` / `docker-compose.yml` in this repo currently even
though older docs reference them — don't assume they exist; check before
citing them.

## Core workflow

The scripts are independent CLI tools with no shared driver — the safe order
is a human/CI convention, not enforced in code:

```bash
python3 render.py                        # build rendered/*.cfg locally, no device contact
python3 verification/healthcheck.py      # confirm network healthy BEFORE the change
python3 deploy.py --yes                  # push rendered/*.cfg (add --limit PE2 to scope to one device)
python3 verification/healthcheck.py      # confirm network still healthy AFTER
python3 save.py                          # write memory — only once verified good
```

`deploy.py` refuses to push and just prints this sequence if `--yes` is
omitted (exit 0). Never remove or bypass that gate.

Other commands:

```bash
python3 test_template.py <template.j2> <host> [host2 ...]   # e.g. test_template.py bgp.j2 pe1 pe2
python3 collect.py --task <ospf|ldp|bgp|vrf|mpls|ce|all> [--host H ...] [--group core|ce]
python3 verification/healthcheck.py --baseline        # (re)capture baseline.json after a confirmed-healthy state
python3 verification/healthcheck.py --host pe1 p1     # scope health check to specific hosts
```

`collect.py` and `verification/healthcheck.py` are different trust levels:
`collect.py` dumps raw, unparsed `show` output for a human to eyeball;
`healthcheck.py` is structured/TextFSM-parsed/pass-fail against
`verification/baseline.json`, and is only meaningful once a human has used
`collect.py` to bless the baseline state.

`verification/healthcheck.py` lives one directory below the project root, but
`config.yaml`/`inventory/*.yaml` are shared with `deploy.py`/`collect.py`/
`save.py` and stay at the root — the script sets `ROOT_DIR = dirname(BASE_DIR)`
and does `os.chdir(ROOT_DIR)` (not `BASE_DIR`) before `InitNornir(...)` for
exactly this reason. `BASE_DIR` (the script's own dir) is still used for
`baseline.json`, `textfsm/`, and `logs/` — keep that split if you edit it.

## Secrets

Every real credential (`username`/`password`/enable `secret`/OSPF auth
key/BGP peer password) is a `"${VAR_NAME}"` placeholder in the YAML, resolved
from environment variables at runtime — never commit a real value into
`inventory/*.yaml` or `host_vars/*.yaml`. `.env.example` lists every required
var; `.env` (gitignored) holds the real ones locally, loaded via
`python-dotenv`.

There are **two separate resolution call sites**, matching the same
render.py-vs-Nornir split documented below — they don't unify:

- **Nornir path** (`deploy.py`/`collect.py`/`save.py`/`verification/healthcheck.py`):
  `nornir_transform.py`'s `inject_credentials` is registered as a Nornir
  `transform_function` (via `TransformFunctionRegister.register(...)`, called
  manually before `InitNornir()` — `config.yaml`'s `transform_function` value
  is looked up by **name** in that registry, not imported as a dotted path;
  there's no packaging/entry-points setup in this repo, so the registration
  call is required in every script that uses it). It runs once per host after
  inventory load, resolving `username`/`password` (which `Host.__getattribute__`
  already merges host→group→defaults on every read) and the netmiko `secret`
  (which is **not** covered by that merge — `extras` merges as a whole dict,
  not per-key — so the function reads the already-merged `extras` via
  `host._get_connection_options_recursively("netmiko")`, resolves just
  `secret` in place, and writes it back at host level).
- **Manual path** (`render.py`/`test_template.py`): neither calls
  `InitNornir()` (see the existing gotcha below), so the transform_function
  never runs for them. They call `secrets_resolver.resolve_deep()` directly on
  their own `{**defaults, **host_data}` dict before rendering.

## Data flow & templating conventions

- **YAML holds decisions, Jinja2 only loops and substitutes.** Don't put
  conditional logic that depends on business meaning into templates if it
  can live in `host_vars/*.yaml` instead.
- `render.py` reads `host_vars/*.yaml` directly via glob — it does **not**
  go through `inventory/hosts.yaml`. Rendering and the Nornir inventory used
  for `deploy.py`/`verification/healthcheck.py`/`collect.py`/`save.py` are
  two separate paths that happen to be keyed by the same hostnames.
  `host_vars/` is a hand-rolled convention, not a Nornir feature — Nornir's
  `SimpleInventory` only ever loads the three files named in `config.yaml`.
  Ansible-style `host_vars/` auto-loading exists in Nornir only via the
  separate `nornir-ansible` plugin, which this repo doesn't use. Don't move
  `host_vars/` under `inventory/` — that would imply Nornir loads it
  automatically, which it doesn't.
- The Nornir scripts load `config.yaml` (`InitNornir(config_file=...)`),
  which points at the `inventory/*.yaml` files and sets the threaded runner.
  Paths in `config.yaml` are CWD-relative, so each script does `os.chdir(...)`
  to the project root first — `deploy.py`/`collect.py`/`save.py` chdir to
  their own `BASE_DIR` (they live at the root); `verification/healthcheck.py`
  chdirs to `ROOT_DIR` (`dirname(BASE_DIR)`) instead, since it lives one
  level deeper. Keep that distinction if you edit any of these scripts.
- Per-host render data is `{**defaults, **host_data}` — `inventory/defaults.yaml`
  is the base, `host_vars/<host>.yaml` overrides on conflict.
- `templates/master.j2` composes other templates by `role`
  (`pe`/`p`/`rr`/`ce`), e.g. `vrf.j2` and `bgp_pe_ce.j2` only for `pe`,
  `bgp_ce.j2` only for `ce`. `role` lives in both `host_vars/<host>.yaml`
  and `inventory/hosts.yaml` (`data.role`) and also drives which show
  commands `verification/healthcheck.py`/`collect.py` run per device.
- Output filenames are lowercase: `rendered/<hostname.lower()>.cfg`.

## CI/CD (Jenkins)

Multibranch pipeline (`Jenkinsfile`), same validation on every branch/PR,
deploy only on `main`:

```
Quick Syntax Checks   py_compile on all *.py, yamllint on host_vars/ + inventory/
Setup venv            fresh venv, pip install -r requirements.txt
Template Syntax Check  Jinja2 parse check on every templates/*.j2
Render Configs         python3 render.py (wrapped in withCredentials: lab-ospf-auth-key, lab-bgp-peer-password)
Validate               python3 ci/check_vrf_consistency.py + ci/check_data_consistency.py
Deploy (main only)     verification/healthcheck.py -> deploy.py --yes -> verification/healthcheck.py -> save.py
                       (wrapped in withCredentials: lab-router-admin-creds, lab-router-enable-secret)
Tag last successful    force-moves git tag `last_deploy_tag` to the deployed commit (main only)
```

There is no unit/integration test suite (no pytest). "Running the tests"
locally means replicating the syntax-check and validate stages above:
`py_compile`, `yamllint`, the Jinja2 parse check,
`ci/check_vrf_consistency.py`, and `ci/check_data_consistency.py`.

## Conventions & gotchas

Distilled from real incidents (full writeups in `README.md`):

- **Separate consecutive `address-family` blocks with a bare `!`** inside
  Jinja2 loops (see `vrf.j2`, `bgp_pe_ce.j2`). IOS's CLI parser rejects two
  back-to-back `address-family`/`exit-address-family` blocks pushed via
  `netmiko_send_config` without a separator, even though the same text
  pastes fine by hand. `deploy.py` preserves bare `!` lines for exactly this
  reason (it only strips blank lines and `!`-prefixed comment text) — don't
  change that filter.
- **RD/RT changes are additive-only via config push** — Netmiko config-merge
  only adds lines textually absent from running-config; it won't detect "this
  value is wrong now." `ci/check_vrf_consistency.py` is the guardrail against
  this class of bug — keep it passing, don't work around it.
- **Legacy IOS SSH crypto** (hmac-sha1 MACs, older KEX groups). Don't bump
  Paramiko/netmiko/ssh library versions without checking they still
  negotiate with these devices — this has broken connectivity twice via two
  different libraries.
- Don't hand-edit `rendered/*.cfg` — it's build output. Edit
  `templates/*.j2` or `host_vars/*.yaml` and re-run `render.py`.
- `verification/baseline.json` and `nornir.log` are gitignored and
  environment-specific — regenerate via `verification/healthcheck.py
  --baseline`, don't hand-edit or commit them.
- Never hardcode a real secret value back into `inventory/*.yaml` or
  `host_vars/*.yaml` "to make testing easier" — that's exactly the mistake
  this repo's `.env`/`${VAR}` convention (see "Secrets" above) exists to
  prevent. If a script can't find a var, fix `.env`, don't patch the YAML.
- `useful_tips/` holds older draft notes that predate VRF_B, CI, and Jenkins
  — treat `README.md` as the source of truth if they conflict.
