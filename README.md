# unifi-lab-kit

[![ci](https://github.com/thc1006/unifi-lab-kit/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/thc1006/unifi-lab-kit/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)
[![python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](./pyproject.toml)

> Reproducible **reset-and-reconfigure** toolkit for a small lab network:
> one UniFi Security Gateway, one UniFi switch, ~10 Ubuntu GPU servers, one NAS.
>
> If your router was reset, your port-forwards vanished, and you need to
> re-provision the whole thing from a laptop — this is for you.

---

## Tested environment

**This is the exact combination we verified end-to-end on 2026-03-03. Drift from any of these and mileage may vary.**

| Layer                | Component                                              | Version / Firmware                   |
| -------------------- | ------------------------------------------------------ | ------------------------------------ |
| Gateway              | Ubiquiti UniFi Security Gateway 3P (USG-3P)            | EdgeOS 4.x (stock shipping firmware) |
| Switch               | Ubiquiti UniFi Switch 16 150W (US-16-150W)             | stock firmware (unmanaged here)      |
| Controller           | `lscr.io/linuxserver/unifi-network-application:latest` | UniFi Network 8.x (Jan 2026 image)   |
| Controller host      | NAS, Docker 24+, macvlan + ipvlan networks             |                                      |
| NAS OS               | Ubuntu-based NAS                                       | kernel 6.x                           |
| NAS Samba            | native `samba`, installed via `apt`                    | 4.15.13                              |
| Servers              | Ubuntu 20.04 / 22.04 / 24.04 LTS                       | netplan or NetworkManager            |
| Python (this toolkit) | CPython                                                | 3.10, 3.11, 3.12                     |
| Python deps          | `paramiko`, `python-dotenv`, `pyyaml`, `requests`      | see `pyproject.toml`                 |

Tooling runs from any Linux / WSL / macOS workstation that can reach the LAN (or the WAN via SSH).

---

## TL;DR — one-paragraph description

`unifi-lab-kit` is a thin Python package (`unifi_lab_kit`) fronted by a `Makefile`.
Every action ("provision USG", "sync Controller rules", "deploy SSH keys", "install Samba on NAS", "verify end-to-end") is a `make` target.
Credentials and IPs are read from a local `.env` (see `.env.example`) — **no secrets in code, nothing sensitive committed**.
The "how we discovered this" scripts (~85 one-shot iterations) live under `archive/2026-03-03-initial-recovery/` so history stays discoverable without polluting the top level.

---

## Quickstart

```bash
# 1. Clone and set up the virtualenv
git clone https://github.com/thc1006/unifi-lab-kit.git
cd unifi-lab-kit
make install                  # creates .venv and installs the package

# 2. Provide your site-specific secrets
cp .env.example .env
$EDITOR .env                  # fill WAN_IP, USG_PASS, CONTROLLER_PASS, NAS_PASS, SERVER_PASS, ADMIN_SSH_PUBKEY

# 3. (Optional) customise inventory
cp inventory/hosts.example.yml inventory/hosts.yml
$EDITOR inventory/hosts.yml   # list your servers, MAC addrs, port-forward ports

# 4. Run diagnostics first — no secrets needed, purely read-only
make diagnose

# 5. Provision
make provision                # USG + Controller + SSH keys + static IPs, in order
make samba-install            # NAS native Samba (optional)

# 6. Verify
make verify
```

See `docs/RUNBOOK.md` for step-by-step recovery procedures, including what to do when the USG was factory-reset, when the Controller lost its database, or when a new server joins the lab.

---

## Repo layout

```
unifi-lab-kit/
├── README.md                   ← you are here
├── LICENSE                     ← Apache-2.0
├── Makefile                    ← make diagnose | provision | verify | reset
├── pyproject.toml              ← PEP 621 metadata (ruff, pytest, hatch)
├── .env.example                ← credentials template — copy to .env
├── .gitignore
│
├── configs/                    ← infrastructure config templates
│   ├── config.gateway.json.example    # USG NAT hairpin + WAN alias
│   ├── smb.conf.template              # NAS Samba shares
│   └── ssh_config.example             # client-side SSH aliases
│
├── inventory/
│   └── hosts.example.yml       ← devices, MACs, port-forwards (data, not code)
│
├── src/unifi_lab_kit/              ← Python package (paramiko-based)
│   ├── config.py                      # loads .env
│   ├── usg.py                         # EdgeOS CLI provisioning
│   ├── controller.py                  # UniFi Controller REST API sync
│   ├── controller_pwreset.py          # Mongo admin password reset
│   ├── ssh_deploy.py                  # SSH key + NOPASSWD sudo deploy
│   ├── scan.py                        # identify unknown hosts by credential probe
│   ├── static_ip.py                   # convert netplan/nmcli to static
│   ├── nas_samba.py                   # native Samba install on NAS
│   └── verify.py                      # post-deploy audit
│
├── scripts/                    ← shell helpers (no credentials)
│   ├── diagnose.sh             # network reachability probe
│   └── tcp_portscan.sh         # WAN port + internal SSH sweep
│
├── docs/
│   ├── NETWORK_TOPOLOGY.md     ← redacted architecture reference
│   ├── RUNBOOK.md              ← "the network is down, do this" procedures
│   ├── architecture.md         ← Mermaid C4 diagrams
│   └── adr/                    ← numbered architecture decision records
│       ├── 0001-edgeos-cli-over-controller.md
│       ├── 0002-native-samba-over-docker.md
│       ├── 0003-port-445-blocked-workarounds.md
│       └── 0004-paramiko-over-ansible.md
│
├── tests/                      ← pytest scaffolding (future)
│
├── archive/                    ← read-only history — do NOT modify
│   └── 2026-03-03-initial-recovery/
│       ├── README.md                  # explains what's here and why
│       └── *.py / *.sh                # 85+ one-shot recovery scripts
│
└── _secrets/                   ← local-only, gitignored
    └── README.md                      # place .env copy, private CSV, etc. here
```

---

## What this does *not* do

- **It is not Ansible.** The point is to run a handful of imperative Python scripts from a laptop, not to manage hundreds of devices declaratively. If your lab grows past ~20 hosts, migrate to Ansible or Nornir — the `src/unifi_lab_kit/` layout maps cleanly to roles.
- **It is not MBSE.** For a lab this size, SysML/Cameo ceremony costs more than it buys. We use ADRs + Mermaid C4 + YAML inventory instead — see `docs/adr/` for the reasoning.
- **It is not vendor-agnostic.** Tested only against the specific hardware and firmware listed in the table above. Different UniFi firmware may have different CLI syntax.

---

## Safety

- All scripts default to **dry-run off** — they *do* make changes. Review the file before the first invocation.
- Destructive operations (`make reset`, `python -m unifi_lab_kit.usg --reset`, `python -m unifi_lab_kit.controller --reset`) all require `CONFIRM=yes` in the environment. The gate is enforced in Python so it cannot be bypassed by invoking the module directly.
- **SSH host-key trust:** `paramiko.AutoAddPolicy` is used throughout, meaning the tool will accept and silently pin any SSH host key on first contact. This is deliberate — the whole point of the toolkit is to reset hardware whose host keys *will* change. If you run this on a stable, production-grade network, override the policy by seeding `~/.ssh/known_hosts` ahead of time and patching `src/unifi_lab_kit/_ssh.py` to use `RejectPolicy`.
- **Credential hygiene:** everything sensitive lives in `.env` (gitignored). Real inventories (CSV, MAC lists, USG config.boot backups) belong in `_secrets/`, which is also gitignored. See `SECURITY.md` for the vulnerability-disclosure process.

---

## Contributing

See `CONTRIBUTING.md`. The short version: keep `src/unifi_lab_kit/` credentials-free (everything from `.env`), add a test where you can, and if you supersede an existing flow, move the old one into `archive/` with a dated sub-folder — don't delete history.

## License

Apache License 2.0 — see `LICENSE`.
