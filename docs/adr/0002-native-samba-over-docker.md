# ADR-0002: Use native Samba on the NAS host, not a containerised Samba

- **Status:** Accepted
- **Date:** 2026-03-03

## Context

The NAS originally served SMB via a Docker container on a `macvlan` bridge parented to a secondary NIC. When that NIC went down, every client lost its file share — and the container wasn't obviously broken, it was just on a dark bridge.

The failure mode was hard to diagnose (container "Running", port "listening", just on an interface with no link). We needed a configuration that degrades less silently.

## Decision

**Install `samba` from the distro package manager on the NAS host itself.** Bind explicitly to the LAN IP and restrict `hosts allow` to the LAN subnet. Manage via systemd.

See `src/mllab_net/nas_samba.py` and `configs/smb.conf.template`.

## Consequences

- **Pros**
  - Single point of failure collapses: if the NAS's physical NIC is up, SMB is up. No macvlan bridging to reason about.
  - `systemctl status smbd` gives a definitive answer about whether the service is live.
  - Upgrade path is the OS's normal `apt upgrade samba` — no image pinning.
- **Cons**
  - Less isolation than a container. Mitigated by binding to the LAN IP only and configuring `hosts allow = 192.168.1.0/24 / hosts deny = 0.0.0.0/0`.
  - Tested on Samba 4.15.13 only. Config has been stable across the 4.15 to 4.19 range, but if you run 4.13 or earlier, `server min protocol = SMB2_10` may need adjustment.

## Alternatives considered

- **Keep the containerised Samba, move it to an `ipvlan` on the active NIC.** Rejected because the extra abstraction buys nothing over native `smbd` once we accept the "NAS is the host" framing.
- **Switch to NFS.** Client OS on the lab is primarily Windows; SMB is the more ergonomic protocol. NFS remains an option if the client mix shifts.
