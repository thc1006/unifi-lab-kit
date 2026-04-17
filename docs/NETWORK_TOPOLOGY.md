# Network topology (reference)

> Redacted architecture snapshot of the reference lab the toolkit was built
> against. Treat this as a *shape* guide — all real values (IPs, MACs,
> credentials) live in your local `.env` and `inventory/hosts.yml`, which are
> gitignored.

---

## Layers

```
                   University backbone (public /24)
                              │
                 WAN_IP  (static, assigned by IT)
                 WAN_GATEWAY
                              │
                   ┌──────────┴──────────┐
                   │      USG-3P         │   LAN: 192.168.1.1
                   │   (EdgeOS CLI)      │   Port-forwards defined here,
                   └──────────┬──────────┘   NOT in Controller UI.
                              │
                   ┌──────────┴──────────┐
                   │   US-16-150W        │
                   │   UniFi Switch      │
                   └──────────┬──────────┘
                              │
     ┌────────┬───────────────┼────────────────┬────────┐
  Servers   NAS (.129)       PCs           Unknown     Admin laptop
  (.106–.123)
               │
               └── Docker: UniFi Controller + wan-nginx + Samba + …
```

Key facts that drove the design choices:

- The USG is provisioned **from the EdgeOS CLI, not from the Controller UI**. Controller provisioning has overwritten WAN/port-forward settings in the past. See `docs/adr/0001-edgeos-cli-over-controller.md`.
- Samba is served by a **native `samba` package on the NAS host**, not a Docker container. See `docs/adr/0002-native-samba-over-docker.md`.
- Port 445 is **blocked by the upstream backbone**, so external SMB is impossible. Use SFTP/SSHFS/VPN instead. See `docs/adr/0003-port-445-blocked-workarounds.md`.

---

## Port-forward convention

External port = `12` + last-two-digits-of-internal-IP.

| Internal host    | Internal IP       | External port |
| ---------------- | ----------------- | ------------- |
| server-N         | `.10N` or `.11N`  | `120N0` / `121N0` |
| NAS              | `.129`            | `12990`       |

All rules forward WAN:external_port to internal_ip:22 (TCP only). The actual list for your deployment lives in `inventory/hosts.yml`.

---

## NAS Docker network architecture

The NAS has two physical NICs. In production only one is active; the other is a historical artefact.

```
NAS physical:
  NIC-A (active) ── Switch ── USG ── WAN
  NIC-B (DOWN)     legacy subnet, services on this bridge are unreachable

Docker macvlan "wan" (parent: NIC-A):
  subnet = public /24, gw = WAN_GATEWAY
  containers take WAN IPs directly, bypassing USG NAT
  ├── nginx reverse proxy  (public IP #1)
  └── UniFi Controller     (public IP #2)

Docker macvlan "legacy-nat" (parent: NIC-B, ⚠ NIC-B DOWN):
  historical internal subnet; services here are dark
  └── [old SMB container, Nextcloud, HackMD, Overleaf, Pi-hole, MinIO]

Docker ipvlan "lan" (parent: NIC-A):
  subnet = LAN_SUBNET, gw = LAN_GATEWAY
  for future containers that should live on the main LAN

Host shim (legacy-nat-host@NIC-A):
  lets the NAS host itself talk to containers on the dead legacy-nat bridge
  via kernel routing
```

If you're standing up a new NAS from scratch, skip the legacy-nat bridge — it only exists because an old cabling layout left it there.

---

## Gotchas captured from real incidents

- **Controller Force-Provision will wipe EdgeOS CLI settings.** Always edit `/config/config.boot` on the USG directly.
- **`commit` on EdgeOS is not atomic across reboots.** You must `save` after `commit`, or reboots revert the change.
- **UniFi Controller stores port-forwards separately from what the USG actually applies.** After manual USG edits, run `ulk-controller` to resync so the Controller doesn't re-push stale data on the next provision.
- **NAS macvlan containers cannot ping the NAS host by default** because of Linux kernel bridging rules. The `host shim` veth is the standard workaround.

---

## See also

- `docs/RUNBOOK.md` — step-by-step recovery procedures
- `docs/architecture.md` — Mermaid C4 diagrams (renders on GitHub)
- `docs/adr/` — architecture decision records
- `inventory/hosts.example.yml` — data model for hosts / ports / MACs
