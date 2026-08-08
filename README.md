# MPLS L3VPN Network Automation — Nornir + Jenkins CI/CD

A network automation project built on a 10-router Cisco IOS MPLS L3VPN lab (GNS3/IOU). Nornir, Python, and Jinja2 generate, check, and push router configs, wired into a Jenkins CI/CD pipeline that only deploys after a pull request is merged to `main`.

> **Companion repos:**
> [`myansible-lab`](https://github.com/umiseaz/myansible-lab) — the same lab and the same Jinja2 templates, automated with Ansible instead of Nornir. Built side by side so the two tools can be compared directly.
> [`mypyats-lab`](https://github.com/umiseaz/mypyats-lab) — the same lab, checked with Cisco's own pyATS/Genie framework, plus an AI-assisted layer (MCP + a locally-run model) for asking questions about live device state.

Built to practice real NetDevOps skills: treating infrastructure as code, deploying safely, verifying network health properly, and gating changes through CI/CD — not just rendering templates.

---

## Why this project

Most "network automation" tutorials stop at "render a template, push a config." This one goes further:

- **Checks real device state, not just text** — health checks read live OSPF/LDP/BGP/VPNv4 state with TextFSM and compare it to a known-good baseline. Comparing `show running-config` text directly is unreliable (see [Postmortems](#postmortems) for why).
- **A real CI/CD pipeline in Jenkins** — every branch and pull request gets checked automatically. Only a merge to `main` triggers a real deploy, and every deploy gets tagged so you can tell what's actually running.
- **Real bugs, not a clean demo** — four postmortems below, each with the actual symptom, root cause, fix, and lesson.

---

## Topology

```
AS65 — OSPF / MPLS LDP / iBGP with Route Reflectors

              RR1 (5.5.5.5)         RR2 (6.6.6.6)
                   |                      |
              P1 (2.2.2.2) ────────── P2 (3.3.3.3)
                   |                      |
              PE1 (1.1.1.1)         PE2 (4.4.4.4)
                 /      \              /      \
           CE1(VRF_A) CE3(VRF_B)  CE2(VRF_A) CE4(VRF_B)
           AS65001     AS65002    AS65001     AS65002
```

| Device | Role | Loopback | OOB Mgmt IP |
|---|---|---|---|
| PE1 | PE | 1.1.1.1 | 10.1.1.1 |
| PE2 | PE | 4.4.4.4 | 10.1.1.4 |
| P1 | P | 2.2.2.2 | 10.1.1.2 |
| P2 | P | 3.3.3.3 | 10.1.1.3 |
| RR1 | RR | 5.5.5.5 | 10.1.1.5 |
| RR2 | RR | 6.6.6.6 | 10.1.1.6 |
| CE1 | CE (VRF_A) | 77.77.77.77 | 10.1.1.7 |
| CE2 | CE (VRF_A) | 88.88.88.88 | 10.1.1.8 |
| CE3 | CE (VRF_B) | 99.99.99.99 | 10.1.1.9 |
| CE4 | CE (VRF_B) | 100.100.100.100 | 10.1.1.10 |

Two VRFs: **VRF_A** (rd 65:65001) and **VRF_B** (rd 65:65002), each spanning both PEs.

---

## Tech stack

| Layer | Tools |
|---|---|
| Templating | Jinja2 — 12 role-based templates |
| Automation | Nornir 3.5, Netmiko |
| Parsing / verification | TextFSM, ntc-templates (custom templates for LDP & VPNv4) |
| CI/CD | Jenkins (Docker, custom image), Multibranch Pipeline, GitHub PAT auth |
| Version control | Git / GitHub, feature-branch + PR workflow |
| Lab | GNS3, Cisco IOU, Cisco IOS |

---

## Repository structure

```
templates/             12 Jinja2 templates, one per config feature, combined by device role
host_vars/              One YAML file per device — its interfaces, VRFs, BGP peers, prefix-lists, route-maps
inventory/              Nornir inventory + shared defaults — hosts.yaml is the single source of truth for device role
config.yaml             Nornir config (used by deploy.py/collect.py/save.py/verification/healthcheck.py)
ci/
  check_vrf_consistency.py    Checks RD/RT match across every PE, before any device is touched
  check_data_consistency.py   Checks for duplicate IPs, broken references, and inventory/host_vars mismatches
rendered/              Generated device configs — build output, don't hand-edit
bootstrap/              Minimal configs used only to bring a device up for the first time

render.py              Builds configs only, no device contact — see "How render.py works" below
deploy.py              Pushes configs — requires --yes, supports --limit HOST
save.py                Writes memory ("write mem") on every device
collect.py              Ad-hoc show-command dumper for a human to read; not pass/fail
test_template.py        Renders one template against one host, for quick debugging

verification/           Everything needed to check the network is actually healthy
  healthcheck.py           Captures a baseline, then checks live state against it (--task to limit checks)
  baseline.json            The saved "known-good" state — regenerate after a real topology change
  textfsm/                 Custom parsing templates for commands ntc-templates doesn't cover
  logs/                    One folder per health-check run

Jenkinsfile             The Jenkins CI/CD pipeline
```

The custom Jenkins image (`Dockerfile` with Python, yamllint, git, sshpass,
and legacy SSH settings) and its `docker-compose.yml` live on the Jenkins
host itself, not in this repo.

---

## How render.py works

`render.py` turns per-device YAML into router configs. No SSH, no device
contact — just files in, files out.

1. Reads `inventory/defaults.yaml` (settings shared by every device) and
   `inventory/hosts.yaml` (used only to look up each device's role).
2. Reads every file in `host_vars/*.yaml` — one file per device, holding its
   interfaces, VRFs, BGP peers, prefix-lists, and route-maps.
3. For each device: merges the defaults with that device's data, then sets
   `role` from `inventory/hosts.yaml` — the single source of truth for role.
4. Renders `templates/master.j2` with that merged data. `master.j2` pulls in
   the right sub-templates based on `role` (e.g. only PEs get `vrf.j2`).
5. Writes the result to `rendered/<device>.cfg`.

**One gotcha:** both files use the word "hostname," but they mean different
things. In `host_vars/pe1.yaml`, `hostname: PE1` is the device's *name*. In
`inventory/hosts.yaml`, the `hostname:` field is the device's *management IP*
(e.g. `10.1.1.1`), used by Nornir to actually SSH in. `render.py` matches the
two files by device name only — it never touches the IP.

If a `host_vars` file is broken or missing its `hostname` key, that one
device is skipped and logged — the rest still render. Any missing or
typo'd Jinja2 variable fails the whole render loudly (`StrictUndefined`),
instead of silently producing a blank line in a router config.

---

## The deployment workflow

```
render          → build configs locally, no device contact
collect          → raw show-command dump, human review — is the network genuinely healthy?
healthcheck --baseline  → only after human confirms healthy — capture as reference state
────────────────────────────────────────────────────
render          → build configs for a NEW change
healthcheck     → confirm the network is healthy BEFORE the change
deploy --yes    → push, requires explicit confirmation
healthcheck     → confirm the network is STILL healthy AFTER
save            → write memory, only once verified good
```

```bash
python3 render.py
python3 verification/healthcheck.py
python3 deploy.py --yes
python3 verification/healthcheck.py
python3 save.py
```

`collect.py` and `healthcheck.py` are trusted differently: `collect.py` just
dumps raw `show` output for a person to read; `healthcheck.py` is the strict,
pass/fail check against `baseline.json` — and that baseline is only
trustworthy once a person has used `collect.py` to confirm the network was
actually healthy first.

---

## CI/CD pipeline (Jenkins)

A Multibranch Pipeline watches the GitHub repo. It builds every branch and
pull request, and posts the result straight onto the PR.

```
Feature branch pushed
   → Jenkins auto-triggers (polling, 1 min interval)
   → Quick Syntax Checks   (py_compile, yamllint — fail fast, before venv setup)
   → Setup venv            (isolated per-build, from requirements.txt)
   → Template Syntax Check (Jinja2 parse check)
   → Render Configs
   → Validate              (ci/check_vrf_consistency.py + ci/check_data_consistency.py —
                            RD/RT consistency, reference integrity, duplicate IPs,
                            router-id uniqueness, peer resolution, inventory sync)
   → [Deploy stage SKIPPED — not main]
   → Status reported to GitHub PR

Pull Request → reviewed → merged to main
   → Jenkins auto-triggers on main
   → same validation stages, PLUS:
   → Deploy (healthcheck → deploy --yes → healthcheck → save)
   → Tag `last_deploy_tag` moved to the deployed commit
```

`git log last_deploy_tag..main --oneline` tells you whether `main` has
changes that haven't been deployed to the real devices yet.

> **Note:** GitHub's branch protection rules are turned on but not actually
> enforced — this is a free-tier private repo, and GitHub only enforces
> protection rules on public repos or paid Team/Enterprise plans. The
> PR-first workflow is followed here as team discipline, the same way it
> would run if enforcement were switched on.

---

## Postmortems

Real bugs hit and fixed while building this — not a clean tutorial run.

### 1. IOS rejects a second `address-family` block pushed back-to-back

**Symptom:** `% Invalid input` on `exit-address-family` — reproducible, but
only on PE2, not PE1, even though both had the same kind of data.

**Root cause:** Two `address-family ipv4 vrf X` blocks pushed back-to-back,
with no `!` between them, confuse IOS's CLI parser when pushed by
automation — even though the exact same text pastes in fine by hand, because
a human typing naturally leaves a small delay between lines.

**Fix:** Added an explicit `!` after every `exit-address-family` inside the
Jinja2 loops in `vrf.j2` and `bgp_pe_ce.j2`. `deploy.py` keeps those bare `!`
lines when it pushes config (it only strips blank lines and `!`-comment
lines) so the separators actually reach the device.

**Lesson:** A config being valid IOS and pasting fine by hand doesn't
guarantee it survives an automated bulk push.

### 2. Legacy IOS SSH crypto vs. a modern SSH client (Paramiko)

**Symptom:** `kex error: no match for method mac algo` — Paramiko 5.0
dropped support for `hmac-sha1`, and this lab's IOS image only supports
`hmac-sha1`/`hmac-sha1-96`.

**Fix:** Installed `ansible-pylibssh` and set
`ansible_network_cli_ssh_type: libssh`, which still negotiates those older
algorithms.

**Lesson:** Old Cisco gear is common in the real world. An SSH library
update that "improves security" can quietly break connectivity to it.

### 3. A wrong RD value that config push can't fix on its own

**Symptom:** The same `% Invalid input` error, even after fully rebuilding
`router bgp 65` on the device.

**Root cause:** PE2's `VRF_A` already had the wrong RD saved on the device
(`65:65002`, copy-pasted from VRF_B). Config-merge tools only ever *add*
lines that aren't already in the running config — they can't tell "this
value is wrong now," because fixing that needs an explicit `no rd X` before
the correct `rd Y` can be applied.

**Fix:** Fixed the RD by hand on the device, then added
`ci/check_vrf_consistency.py` as a CI check — every push now checks that
RD/RT values match across all PEs before touching any device.

**Lesson:** Config push tools add, they don't correct. Any value that might
*change* needs either explicit removal logic or a check that catches the
mismatch before it's pushed.

### 4. The same crypto problem came back through a different library

**Symptom:** While setting up the sibling Ansible pipeline's Jenkins job,
deployment failed with `kex error: no match for method kex algos` — a
key-exchange mismatch this time, not MAC.

**Root cause:** Same underlying issue as #2 — legacy IOS crypto vs. a modern
SSH client — but surfacing through `ansible-pylibssh`/`libssh` instead of
Paramiko, in a different environment (Jenkins' own container), with a
different algorithm family (KEX, not MAC).

**Fix:** Baked an `~/.ssh/config` into the Jenkins Docker image with
`KexAlgorithms +diffie-hellman-group14-sha1`, `MACs +hmac-sha1`,
`HostKeyAlgorithms +ssh-rsa`, and `PubkeyAcceptedAlgorithms +ssh-rsa`.

**Lesson:** Spotting that this was *the same kind of problem* as before —
not just "another SSH error" — made it much faster to fix the second time.
Legacy device compatibility keeps coming back; it's worth having a standard
fix ready (relax the specific algorithm on the client side, don't fight the
device).

---

## What this project demonstrates

- Infrastructure as code: data (YAML) and logic (Jinja2) kept separate, so
  the same templates work with two different automation tools and produce
  identical output
- Safe deployment habits: render, deploy, and save kept as separate steps
  that each need explicit confirmation
- Checking real device state instead of just diffing config text, and
  understanding why text-diffing running-config isn't reliable
- CI/CD design: cheap checks run first, branch-aware deploy gating, changes
  reviewed through pull requests
- Real debugging: SSH/crypto issues (twice, through two different
  libraries), IOS CLI quirks, and the limits of idempotent config push — all
  diagnosed with evidence, not guesses
