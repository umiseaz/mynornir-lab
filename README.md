# MPLS L3VPN Network Automation — Nornir + Jenkins CI/CD

A production-style network automation project built on a 10-router Cisco IOS MPLS L3VPN lab (GNS3/IOU): Nornir + Python + Jinja2 generate, validate, and deploy configuration, wired into a Jenkins CI/CD pipeline with branch-protected, PR-gated deployment.

> **Companion repo:** [`myansible-lab`](https://github.com/umiseaz/myansible-lab) — the same topology and Jinja2 templates, automated with Ansible instead, with its own Jenkins pipeline. Built side-by-side to compare the two ecosystems directly.

This project was built to develop real NetDevOps skills: infrastructure-as-code discipline, safe deployment workflows, structured state verification, and CI/CD gating — not just template rendering.

---

## Why this project

Most "network automation" tutorials stop at "render a template, push a config." This project goes further:

- **Functional verification, not text diffing** — health checks parse live device state (OSPF, LDP, BGP, VPNv4) via TextFSM and compare against a known-good baseline, because comparing `show running-config` text is unreliable (see [Postmortems](#postmortems))
- **A full CI/CD pipeline in Jenkins** — every branch and pull request is validated automatically; only merges to `main` trigger a live deploy; deployments are tagged for traceability
- **Real bugs, found and fixed with evidence** — not a clean tutorial run. Four genuinely instructive postmortems below.

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
templates/            12 Jinja2 templates — role-based, identical output to the Ansible repo
host_vars/             Per-device YAML data (10 files)
inventory/             Nornir inventory + shared defaults
textfsm/               Custom TextFSM templates (LDP neighbor, VPNv4 summary)
ci/
  check_vrf_consistency.py   CI gate — catches RD/RT mismatches before deploy
rendered/              Generated device configs (build output)
bootstrap/              Minimal OOB bring-up configs

render.py              Render-only — no SSH, no device contact
deploy.py              Push-only — requires --yes flag, supports --limit HOST
save.py                write memory across all devices
healthcheck.py          Baseline capture + structured health verification
collect.py              Ad-hoc show-command collector (raw output, human-reviewed)
test_template.py        Quick single-template/single-host render for debugging

Jenkinsfile             Branch-aware CI/CD pipeline definition
Dockerfile               Custom Jenkins image (Python, yamllint, git, sshpass, legacy SSH config)
docker-compose.yml       Jenkins deployment (host networking for lab reachability)
baseline.json            Captured healthy-state snapshot — regenerate after real topology changes
```

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
python3 healthcheck.py
python3 deploy.py --yes
python3 healthcheck.py
python3 save.py
```

`collect.py` and `healthcheck.py` serve two different trust levels: `collect.py` dumps raw, unparsed `show` output for a human to judge; `healthcheck.py` is structured, TextFSM-parsed, pass/fail — and is only trustworthy once a human has used `collect.py` to bless the state it's comparing against.

---

## CI/CD pipeline (Jenkins)

A Multibranch Pipeline scans the GitHub repo, builds every branch and pull request, and reports status directly on the PR.

```
Feature branch pushed
   → Jenkins auto-triggers (polling, 1 min interval)
   → Quick Syntax Checks   (py_compile, yamllint — fail fast, before venv setup)
   → Setup venv            (isolated per-build, from requirements.txt)
   → Template Syntax Check (Jinja2 parse check)
   → Render Configs
   → Validate              (ci/check_vrf_consistency.py — RD/RT consistency across PEs)
   → [Deploy stage SKIPPED — not main]
   → Status reported to GitHub PR

Pull Request → reviewed → merged to main
   → Jenkins auto-triggers on main
   → same validation stages, PLUS:
   → Deploy (healthcheck → deploy --yes → healthcheck → save)
   → Tag `last_deploy_tag` moved to the deployed commit
```

`git log last_deploy_tag..main --oneline` answers "is `main` ahead of what's actually running on the devices."

> **Note:** GitHub branch protection rules are configured but not enforced — this is a free-tier private repo, and GitHub only enforces protection rules on public repos or paid Team/Enterprise plans. The PR-gated workflow is followed as team discipline, matching how it would run in an enforced environment.

---

## Postmortems

Real bugs hit and diagnosed during this build.

### 1. IOS rejects a second `address-family` block pushed back-to-back

**Symptom:** `exit-address-family` / `exit-address-family` — `% Invalid input` — reproducible, but only on PE2, not PE1, despite identical data structures.

**Root cause:** Two consecutive `address-family ipv4 vrf X` blocks pushed via `netmiko_send_config` with no `!` separator between them confuse the IOS CLI parser under live automation, even though the exact same text pastes cleanly by hand into a console with natural typing delay.

**Fix:** Added an explicit `!` after every `exit-address-family` inside the Jinja2 loops in `vrf.j2` and `bgp_pe_ce.j2`.

**Lesson:** A config that's syntactically valid IOS and pastes fine by hand is not the same guarantee as a config that survives automated bulk push.

### 2. Legacy IOS SSH crypto vs modern SSH clients (Paramiko)

**Symptom:** `kex error: no match for method mac algo` — Paramiko 5.0 dropped `hmac-sha1` support; the lab's IOS image only supports `hmac-sha1`/`hmac-sha1-96`.

**Fix:** Installed `ansible-pylibssh` and set `ansible_network_cli_ssh_type: libssh`, which negotiates legacy algorithms Paramiko refuses by default.

**Lesson:** Legacy Cisco gear is common in the real world; SSH library version bumps that "improve security" can silently break connectivity to it.

### 3. A stale RD value that idempotent config push can't self-correct

**Symptom:** Same `% Invalid input` error, persisted even after a full `no router bgp 65` rebuild on the device.

**Root cause:** `PE2`'s `VRF_A` had the wrong RD (`65:65002`, copy-pasted from VRF_B) already pushed and saved. Config-merge tools only ever *add* lines that are textually absent from the running-config — they don't detect "this value is wrong and needs to change," because that requires an explicit `no rd X` before the new `rd Y` can apply.

**Fix:** Manually corrected the device-side RD, then added `ci/check_vrf_consistency.py` as a CI gate — every push now checks RD/RT consistency across all PEs *before* any device is touched.

**Lesson:** Idempotent config push tools are additive by default. Value *changes* need either explicit removal logic or a data-layer consistency check.

### 4. The same crypto problem resurfaced through a completely different library

**Symptom:** Building the sibling Ansible pipeline's Jenkins job, deployment failed with `kex error: no match for method kex algos` — a *key exchange* mismatch this time, not MAC.

**Root cause:** Same root issue as postmortem #2 (legacy IOS crypto vs. a modern SSH client), but surfacing through `ansible-pylibssh`/`libssh` instead of Paramiko, in a completely different environment (Jenkins' own containerized Python), with a different algorithm family (KEX, not MAC) and a different mismatched pair of clients.

**Fix:** Baked an `~/.ssh/config` with `KexAlgorithms +diffie-hellman-group14-sha1`, `MACs +hmac-sha1`, `HostKeyAlgorithms +ssh-rsa`, `PubkeyAcceptedAlgorithms +ssh-rsa` directly into the Jenkins Docker image.

**Lesson:** Recognizing a bug as *the same class of problem as before* — not just "another SSH error" — made diagnosis much faster the second time. Legacy device compatibility is a recurring category, not a one-off; it's worth having a standard playbook for it (relax specific algorithms at the client, don't fight the device).

---

## What this project demonstrates

- Infrastructure-as-code: data (YAML) and logic (Jinja2) cleanly separated, portable across two different automation engines (see the Ansible sibling repo) with byte-identical output
- Safe deployment discipline: render/deploy/save as distinct, explicitly-gated steps
- Structured state verification over naive config diffing, with a clear understanding of *why* text-diffing running-config is unreliable
- CI/CD pipeline design: fast-fail checks before expensive ones, branch-aware stage gating, PR-based review workflow
- Real-world debugging: SSH/crypto compatibility (twice, via two different libraries), IOS CLI automation quirks, and idempotency limitations — diagnosed with evidence, not guesswork

