# ADR-0001: Provision USG via EdgeOS CLI, not via the Controller UI

- **Status:** Accepted
- **Date:** 2026-03-03
- **Deciders:** unifi-lab-kit contributors

## Context

The UniFi Security Gateway can be configured in two ways:

1. **UniFi Network Controller UI / API** — the officially advertised path.
2. **Direct EdgeOS CLI** (`configure; set …; commit; save`) on the USG itself — the underlying router's native interface.

During the 2026-02 through 2026-03 recovery we hit the Controller path twice. Both times, a subsequent "Force Provision" from the Controller UI silently overwrote port-forward rules we had just set up. Debugging took hours because the Controller UI continued to display the *intended* rules while the running `config.boot` on the USG had the stale/wrong ones.

## Decision

**Port-forwards, WAN static IP, and NAT hairpin rules are set directly in the USG's EdgeOS CLI and saved into `/config/config.boot`.** The Controller is treated as a *reflection* of that state — we resync Controller rules to match the USG (via `ulk-controller`), never the other way around.

## Consequences

- **Pros**
  - Changes survive Controller provisioning events.
  - The USG `/config/config.boot` file is the single source of truth; easy to back up and diff.
- **Cons**
  - The Controller UI can still show stale rules if someone edits them there — `make provision-controller` is the reconciliation step and must be run after every USG change.
  - If the USG is fully factory-reset (lost `config.boot`), we re-apply from `unifi_lab_kit.usg` — it's idempotent.

## Alternatives considered

- **Config-gateway JSON shipped via Controller** (`config.gateway.json`): works for NAT hairpin and interface aliases, but does not reliably cover port-forwards across Controller versions. Kept as a supplement (see `configs/config.gateway.json.example`), not the primary mechanism.
- **Ansible `ansible.netcommon.cli_command`**: would work, but adds a framework that pays off only at >20 devices.
