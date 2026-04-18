# Security policy

## Supported versions

This project is pre-1.0. Only the tip of `main` is supported.

| Version        | Status        |
| -------------- | ------------- |
| `main` (HEAD)  | supported     |
| any older tag  | unsupported   |

## Reporting a vulnerability

**Please do not file public GitHub issues for security problems.**

Use GitHub's private vulnerability-report flow:

1. Visit <https://github.com/thc1006/unifi-lab-kit/security/advisories/new>.
2. Describe the issue, ideally with a minimal reproduction.
3. Include the affected commit SHA and your tested environment.

Target response times (best-effort, not guarantees):

- Acknowledgement within 3 business days.
- Patch on `main` within 14 days for high/critical issues.

If you cannot use GitHub Security Advisories, open a placeholder issue
("security report incoming, no details") and we will arrange a private
channel.

## Scope

In scope:

- Credential or IP leakage through committed files (patterns matching
  the scrubbed set tracked in `.github/scripts/secret_regression_scan.sh`,
  or other secrets that would fall out of a plain `git grep`).
- Command injection via `.env` values or `inventory/hosts.yml` (the tool
  shells out to `paramiko.exec_command`; any missing quoting that lets a
  value escape its argument is in scope).
- Privilege escalation on managed hosts (e.g. the `NOPASSWD` rule
  written by `ssh_deploy` being broader than expected).
- MITM / spoofing that the toolkit fails to detect in scenarios the
  README marks as "stable production" (for the reset scenario,
  `AutoAddPolicy` is documented intended behaviour — see below).

Out of scope / accepted risks:

- **SSH first-contact host-key trust.** The toolkit uses
  `paramiko.AutoAddPolicy`. Under the reset/reconfigure workflow this is
  intentional (hardware was just reset; host keys changed). If you run
  the toolkit on a steady-state network, seed `known_hosts` first and
  switch to `RejectPolicy` in `src/unifi_lab_kit/_ssh.py`. See
  `docs/adr/0001-edgeos-cli-over-controller.md` and the README "Safety"
  section for the full trust argument.
- Secrets that live only in a user's local `_secrets/` directory — that
  path is gitignored and never shipped.
- Historical `archive/` scripts. They are frozen and not imported by
  the package. Reports about the shape of legacy logic are welcome, but
  we will not change archive code — only document or replace it.

## Known trust assumptions

1. The operator already has LAN-adjacent access or SSH-via-WAN access
   to the target gateway, NAS, and servers. The toolkit does not
   pivot, does not brute-force, and does not assume compromise.
2. `.env` is supplied by a trusted operator. Invalid or malicious
   values will cause predictable failures, not silent escalation.
3. The UniFi Controller is trusted within the LAN boundary; we do not
   pin its TLS certificate (the `curl -sk` calls inside the container
   talk to `localhost:8443`).

## History

The toolkit was originally written as a bundle of one-shot recovery
scripts with embedded credentials. Before the first public commit
(`8bbd721`) every concrete password, public IP, MAC, personal email,
and SSH public-key body was replaced with a placeholder. The
placeholder set is documented in the commit that introduced
`archive/2026-03-03-initial-recovery/`, and a regression scanner in
`.github/scripts/secret_regression_scan.sh` fails CI if any of those
patterns reappears.
