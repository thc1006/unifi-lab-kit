# Archive — initial recovery (2026-03-03)

> **Status: read-only history. Do not modify. Do not import from here.**

This folder preserves the ~85 one-shot Python / Shell scripts that were
written during the 2026-02-27 to 2026-03-03 emergency recovery of the
reference lab. Each file worked well enough on that one day to get the
network back up, but most are throwaway iterations (`v1 → v2 → v3 →
ultimate_*`) and none of them separate secrets from logic.

They are kept here, not deleted, because:

1. **Discoverability beats git-log**. A future contributor debugging a
   weird symptom can search this folder by filename instead of writing
   a `git log --all -p -S` over a 100-commit history.
2. **Unplanned corner cases are documented by example**. Some of these
   scripts encode a workaround for a specific hardware or firmware quirk
   that isn't captured anywhere else (for instance, `usg_wsl.sh`
   documents the `sshpass`/`expect` dance needed when USG defaulted to
   interactive password prompts).
3. **A few are still borderline-useful as one-off tools** — e.g.
   `brute_all.py` is the nuclear-option credential probe, and
   `reboot_servers.py` is a convenient sequential rebooter.

## What replaces what

| Concern                  | Use now (in `src/mllab_net/` or elsewhere) | Historical scripts here            |
| ------------------------ | ------------------------------------------ | ---------------------------------- |
| USG WAN + port-forwards  | `usg.py`                                   | `fix_usg_final.py`, `usg_direct_fix.py`, `fix_usg_*.py`, `usg_final.py`, `usg_edgeos.py` |
| Controller sync / adopt  | `controller.py`                            | `reconnect_controller.py`, `fix_all_portforward.py`, `adopt_usg.py`, `fix_controller_*.py`, `harden_and_extras.py` |
| Controller pw reset      | `controller_pwreset.py`                    | `reset_unifi_pw.py`                |
| SSH key deploy           | `ssh_deploy.py`                            | `deploy_ssh_key.py`, `deploy_keys_and_portfwd.py`, `install_and_jump.py`, `set_password_nopasswd.py` |
| Static IP                | `static_ip.py`                             | `set_all_static_ip.py`, `set_static_ip.py`, `set_dhcp*.py`, `add_dhcp_server11*.py` |
| Scan / identify          | `scan.py`                                  | `identify_servers.py`, `identify_v2.py`, `identify_v3.py`, `ultimate_identify.py`, `fast_identify.py`, `nas_full_scan*.py`, `explore_*.py`, `brute_all.py`, `full_matrix.py`, all `try_*.py`, all `local_*.py`, `jump_scan.py` |
| NAS Samba                | `nas_samba.py`                             | `setup_nas_smb.py`, `nas_keys.py`, `nas_backup.py` |
| Verify                   | `verify.py`                                | `audit_persistence.py`, `verify_external*.py`, `verify_after_disconnect.py`, `final_check.py`, `final_scan.py` |
| Per-server one-offs      | n/a — use `ssh_deploy.py` + `static_ip.py` | `fix_server5.py` through `fix_server21.py`, `reboot_servers.py`, `check_server6_*.py` |
| Shell diagnostics        | `scripts/diagnose.sh`                      | `diagnose_network.sh`, `diagnose_server.sh`, `diag2.sh`–`diag4.sh`, `usg_diag.sh`, `identify_servers.sh`, `fix_usg.sh`, `check_usg_web.sh`, `usg_wsl.sh` |

## Treat these files as dangerous

They contain:
- Hard-coded IP addresses from the original lab
- Hard-coded usernames and passwords (several, tried in sequence)
- Hard-coded SSH public keys
- References to MAC addresses

If you fork this repo to run in your own lab, **do not copy scripts out
of this folder into `src/mllab_net/`** — port whatever logic you need
and route all secrets through `src/mllab_net/config.py`.

CI lint rules should ignore this folder. See the ruff / mypy excludes
configured in `pyproject.toml` (if / when they are added).
