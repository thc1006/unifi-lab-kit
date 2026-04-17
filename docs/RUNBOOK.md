# Runbook

Step-by-step procedures for recovering from specific failure modes. Each
procedure assumes you have already run `make install` and have a filled-in
`.env` file.

---

## 1. USG was factory-reset (or replaced)

**Symptom:** WAN unreachable; port-forwards gone; Controller shows USG as pending adoption.

1. Physically power-cycle the USG and confirm you can reach `192.168.1.1` from a laptop on LAN.
2. Check you can SSH with default creds (`ubnt / ubnt`) — if yes, immediately change the admin password and re-run step 2 with your new creds.
3. Update `.env`: `USG_USER`, `USG_PASS`, `USG_MAC`, `WAN_IP`, `WAN_GATEWAY`.
4. ```bash
   make provision-usg        # sets WAN static + all port-forwards via EdgeOS CLI
   make provision-controller # syncs Controller rules to match
   make verify               # confirms 11 port-forwards are live
   ```

If `provision-usg` fails with "Connection refused" the USG isn't listening for SSH yet — wait 90 s after boot and retry.

---

## 2. Controller database lost / admin password unknown

**Symptom:** you cannot log in to `https://<NAS>:8443`.

If you still have SSH to the NAS:
```bash
# Reset the admin password using the value from .env (CONTROLLER_PASS)
.venv/bin/python -m unifi_lab_kit.controller_pwreset
```
This reaches into the `unifi` Docker container, updates the MongoDB `admin` collection with a new SHA-512 hash, and verifies login.

If the Controller database itself is corrupt, restore from the nightly backup under the Docker volume mount on the NAS, or re-adopt devices from scratch — every real setting is defined on the USG `config.boot`, so a lost Controller is recoverable as long as the USG is intact.

---

## 3. Server won't come up with a predictable IP after reboot

**Symptom:** a server ends up in DHCP pool range (e.g. `.2xx`) instead of its assigned `.1xx`.

```bash
make static-ip      # converts every listed server to static (netplan or nmcli)
make verify
```

The tool detects whether a server uses `netplan` or `NetworkManager` and emits the right config. If the server is already static it skips.

---

## 4. Brand-new / unknown host on LAN

**Symptom:** `nmap -sn` shows an unfamiliar IP, SSH is open, you don't remember the credentials.

```bash
make scan
```
Tries every credential listed in `.env` across every common username (`admin`, `root`, `ops`, custom). On success, dumps hostname / CPU / GPU / MAC for the host. On failure, leaves the SSH banner so you can identify the OS version at least.

If no credential matches, you'll need physical access — document the box in `inventory/hosts.yml` once you've recovered admin.

---

## 5. NAS native Samba not reachable from LAN

```bash
make samba-install      # idempotent; safe to re-run
```

The script installs `samba` via apt if missing, writes `/etc/samba/smb.conf`, binds to the LAN IP only, enables `smbd` via systemd, and verifies from a second host.

**External SMB is impossible** from off-site because port 445 is blocked at the backbone. Use SFTP via the NAS SSH port-forward instead — see `docs/adr/0003-port-445-blocked-workarounds.md`.

---

## 6. Everything is broken

In order:

1. `make diagnose` — identifies whether the issue is LAN, WAN, or host-specific.
2. Check `git log --oneline`; roll back to the `pre-restructure-2026-04-18` tag if a recent change is suspect.
3. Worst case, power-cycle USG → NAS → switch → servers in that order. Wait 60 s between each.
4. Once LAN is back: `make provision && make verify`.

---

## Adding a new server to the lab

1. Cable it in; DHCP will assign a temporary IP.
2. Pick a permanent `.1NN` IP and a free external port (convention `12NN0`).
3. Update `inventory/hosts.yml` with MAC, target IP, port.
4. ```bash
   make deploy-keys           # put admin SSH key on the new host
   make static-ip             # converts the host to static
   make provision-usg         # adds the new port-forward rule
   make provision-controller  # resync Controller
   make verify
   ```

---

## Decommissioning a server

1. Remove its entry from `inventory/hosts.yml`.
2. Run `make provision-usg` — stale rule is gone on next commit.
3. Run `make provision-controller` so the Controller UI matches.
4. (Optional) `ssh`, `sudo rm /etc/netplan/01-static.yaml`, reboot to release the static binding.
