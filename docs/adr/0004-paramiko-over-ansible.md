# ADR-0004: Keep the toolkit as Python + paramiko, don't migrate to Ansible (yet)

- **Status:** Accepted
- **Date:** 2026-04-18

## Context

The toolkit was born as ~95 ad-hoc `paramiko` / `requests` scripts during the 2026-02 to 2026-03 recovery. Industry advice for NetDevOps at scale is **Ansible** (or Nornir), which maps "clone, fill inventory, run one playbook" more ergonomically than a collection of Python scripts.

We considered rewriting `src/unifi_lab_kit/` as a set of Ansible roles before the first open-source release.

## Decision

**Stay on Python + paramiko for now.** Treat Ansible as a documented future migration path, not a prerequisite.

## Consequences

- **Pros**
  - Zero rewrite cost at open-source time. The scripts that verifiably worked on 2026-03-03 keep working.
  - Contributors only need Python knowledge, not Ansible's mental model (handlers, `register`, idempotence conventions).
  - The `src/unifi_lab_kit/<module>.py` layout maps cleanly to Ansible `roles/<module>/tasks/main.yml` later — nothing precludes migration.
- **Cons**
  - No free idempotence guarantee: every script must handle "already-configured" explicitly.
  - Harder to scale past ~20 hosts. At that size, revisit this ADR.

## Alternatives considered

- **Full Ansible-first rewrite** (candidate B in the initial design): rejected for now due to rewrite cost and audience (our typical contributor is a Python-literate lab sysadmin, not an Ansible practitioner).
- **Nornir**: similar end-state to our current package, with nice per-host concurrency. Low-cost migration target if we outgrow serial execution; revisit once we feel serial pain.

## Trigger for revisit

- Lab size grows past ~20 managed hosts, OR
- A second lab adopts the toolkit and maintains their own fork with divergent credentials/IPs — inventory-as-code becomes more valuable than bespoke scripts.
