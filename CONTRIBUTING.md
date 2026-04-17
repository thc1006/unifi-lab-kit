# Contributing to mllab-network

Thanks for considering a contribution. This toolkit is deliberately small and opinionated — please keep it that way.

## Ground rules

1. **No secrets in code or committed files.** Everything that looks like a password, a public IP, a MAC address, or an SSH public key must come from `.env` (via `src/mllab_net/config.py`) or from `inventory/hosts.yml` (local, gitignored). If you find a literal credential anywhere in `src/` or `docs/`, that's a bug — fix it.
2. **Don't break the Makefile contract.** The user-facing verbs are `diagnose`, `provision`, `verify`, `reset`. New functionality should either add a target here or live in `scripts/` as a shell helper. Don't bury important work in undocumented Python submodules.
3. **Archive, don't delete.** If you replace an existing script with a better one, move the old version to `archive/<YYYY-MM-DD>-<topic>/` and update that folder's `README.md`. History matters when debugging why a weird workaround exists.
4. **Pin what you tested.** If you add a dependency or rely on a specific UniFi firmware / Samba version / kernel, update the "Tested environment" table in `README.md`.

## Development

```bash
make install
make lint
make test
```

## Architectural changes

Open an ADR in `docs/adr/` before large structural changes. Copy the style of `0001-edgeos-cli-over-controller.md` — status, context, decision, consequences, alternatives considered. One page, one decision, numbered sequentially.

## Reporting problems

Include:
- UniFi firmware version (`show version` on USG)
- Controller version (`docker exec unifi cat /usr/lib/unifi/webapps/ROOT/WEB-INF/classes/version.properties`)
- Output of `make diagnose`
- Redacted `.env` (strip passwords, keep IPs)
