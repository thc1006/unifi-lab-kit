# ADR-0003: Off-site file access does NOT go over SMB

- **Status:** Accepted
- **Date:** 2026-03-03

## Context

Users expected to mount the NAS SMB share from off-campus. Our upstream backbone **blocks port 445 egress** as a matter of policy. Verified empirically: outbound TCP 445 from a remote host to our WAN IP is dropped before it reaches our USG.

## Decision

**No port-forward for 445 on the USG.** SMB is LAN-only. For off-site file access, we document four tiered options in `docs/RUNBOOK.md` and `docs/NETWORK_TOPOLOGY.md`:

| Option       | Difficulty  | When to recommend                              |
| ------------ | ----------- | ---------------------------------------------- |
| **SFTP**     | zero-setup  | Default. WinSCP / FileZilla / `sftp` over the existing NAS port-forward. |
| **SSHFS**    | low         | User wants a drive-letter mount. WinFsp + SSHFS-Win on Windows.          |
| **Nextcloud** | medium     | User wants web UI; already running as a Docker service on NAS.           |
| **WireGuard VPN** | high    | User needs native SMB semantics; stand up WG on the NAS + forward port.  |

## Consequences

- **Pros**
  - No half-working external SMB that confuses users.
  - SFTP covers 90 % of cases with zero additional infrastructure.
- **Cons**
  - Users accustomed to a mapped drive letter need WinFsp + SSHFS-Win (third-party software).

## Alternatives considered

- **Map SMB to a non-standard port** (e.g. 44500 → 445). Rejected: Windows does not support non-445 SMB natively.
- **Tunnel SMB over SSH** (`ssh -L 44445:NAS:445`). Works but requires every user to maintain a tunnel; not friendly.
