# `_secrets/` — local-only storage

This directory is gitignored. Put anything sensitive that you want to keep
alongside the checkout but **never** want committed:

- Your filled-in `.env` (copy of `../.env`, for bootstrap convenience)
- Actual device-inventory spreadsheets with credentials (`server-inventory.csv`)
- Private keys, backup tarballs of `/config/config.boot` from the USG
- Anything else that looks like a secret

The `.gitignore` contains:

```
_secrets/**
!_secrets/README.md
!_secrets/.gitkeep
```

so only this README and a placeholder `.gitkeep` are ever tracked. Git
`status` will remain clean even if you drop arbitrary files in here.

If you must share a secret with a teammate, use a password manager
(Bitwarden, 1Password, your org's vault) or encrypted email — never a
git commit and never a Slack DM.
