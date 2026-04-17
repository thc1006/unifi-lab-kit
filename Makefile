# unifi-lab-kit — user-facing entry points.
#
# Inspired by kubespray's top-level `cluster.yml` / `reset.yml` / `recover-*.yml`
# pattern: the developer never needs to know which Python module to import;
# every supported action has a make target.
#
# All targets load secrets from .env (see .env.example for the schema).
# Install dependencies first:  make install

PY        ?= python3
VENV      ?= .venv
ACT       = . $(VENV)/bin/activate;

.PHONY: help install diagnose provision provision-usg provision-controller \
        deploy-keys static-ip samba-install scan verify reset clean \
        lint test

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / { printf "  %-22s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install:  ## Create venv and install package with dev deps
	$(PY) -m venv $(VENV)
	$(ACT) pip install --upgrade pip
	$(ACT) pip install -e ".[dev]"

# ---------- Diagnostics (no credentials required) ----------

diagnose:  ## Run read-only network diagnostics from current host
	bash scripts/diagnose.sh

# ---------- Provisioning (requires .env) ----------

provision: provision-usg provision-controller deploy-keys static-ip  ## Full provision (USG + Controller + SSH keys + static IPs)

provision-usg:  ## Configure USG WAN static IP and all port-forward rules via EdgeOS CLI
	$(ACT) $(PY) -m unifi_lab_kit.usg

provision-controller:  ## Sync UniFi Controller port-forward rules with USG
	$(ACT) $(PY) -m unifi_lab_kit.controller

deploy-keys:  ## Deploy admin SSH public key to every server's authorized_keys
	$(ACT) $(PY) -m unifi_lab_kit.ssh_deploy

static-ip:  ## Convert every server to static IP (netplan or nmcli)
	$(ACT) $(PY) -m unifi_lab_kit.static_ip

samba-install:  ## Install native Samba on NAS and expose shares to LAN only
	$(ACT) $(PY) -m unifi_lab_kit.nas_samba

# ---------- Discovery ----------

scan:  ## Identify unknown servers on LAN by probing with known credentials
	$(ACT) $(PY) -m unifi_lab_kit.scan

# ---------- Verification ----------

verify:  ## Post-deploy audit: WAN/port-forward persistence, SSH, static IPs, sudo, keys
	$(ACT) $(PY) -m unifi_lab_kit.verify

# ---------- Recovery ----------

reset:  ## Emergency: reset USG + Controller back to known-good state (requires .env)
	@echo "RESET is destructive. Re-run with CONFIRM=yes to proceed." && test "$(CONFIRM)" = "yes"
	$(ACT) $(PY) -m unifi_lab_kit.usg --reset
	$(ACT) $(PY) -m unifi_lab_kit.controller --reset

# ---------- Dev ----------

lint:
	$(ACT) ruff check src tests

test:
	$(ACT) pytest -q

clean:
	rm -rf $(VENV) dist build *.egg-info .pytest_cache .ruff_cache .mypy_cache
