#!/usr/bin/env bash
# ============================================================================
#  Regression scan for scrubbed credentials.
#
#  This is NOT a general-purpose secret scanner. It is a lightweight fence
#  that rejects any commit which reintroduces one of the specific literal
#  patterns that were scrubbed from this repository before the initial
#  open-source release. Broader coverage comes from the gitleaks job in
#  ci.yml; this scan is targeted at the "did a developer accidentally
#  un-scrub a historical archive file" case, which gitleaks' entropy-based
#  heuristics would miss.
#
#  Maintenance: if you add a new archive cohort that required scrubbing
#  (e.g. a second 2027-xx recovery), extend PATTERNS below AND update the
#  replacement table documented in the relevant archive/<date>/README.md.
#
#  Exits 0 on clean, 1 if any regression is found.
# ============================================================================
set -u

# Known scrubbed patterns. Keep this list in sync with the replacement table
# documented in the commit that introduced archive/ (run `git log --grep
# 'chore: import historical recovery'`).
PATTERNS=(
    'mllab708'
    'mllab912router'
    'mllab912nas'
    'fd8ylFeBeF5a2oxk'
    'Mllab708unifi'
    'nycuml912'
    'nycumled912'
    'mllabserver(4|5|13|15|temp)'
    'mllab91(212|2912|256a1k)'
    # Real public /24 that used to appear before we swapped it for RFC 5737.
    '140\.113\.144\.'
    # Personal / organisational identifiers.
    'hctsai@linux\.com'
    'mllabjtc@gmail\.com'
    'mllab912jtc@gmail\.com'
    # SSH public key body fragment unique to the leaked key.
    'AAAAIOqhKFZy'
    # Hardware MACs captured from the reference lab.
    '2c:4d:54:e9:4e:38'
    'fc:34:97:a3:91:ce'
    'fc:34:97:e3:77:0a'
    'd4:5d:64:d0:67:86'
    '08:62:66:7d:3c:c0'
    'c8:7f:54:0c:60:88'
    '60:cf:84:ad:17:ed'
    '10:7c:61:0d:81:0f'
    '0c:9d:92:c0:b9:16'
    '60:cf:84:ac:70:0e'
    'b4:2e:99:ae:19:9b'
    '74:ac:b9:4e:38:d7'
)

# Paths to exclude:
#   _secrets/        local-only, gitignored; but double-check in case it slipped
#   .github/         this script itself contains the patterns as data
PATHSPEC=(
    ':(exclude)_secrets'
    ':(exclude).github/scripts/secret_regression_scan.sh'
)

rc=0
for p in "${PATTERNS[@]}"; do
    if output=$(git grep --extended-regexp -n "$p" -- "${PATHSPEC[@]}" 2>/dev/null); then
        echo "::error::Pattern '$p' reintroduced:"
        echo "$output" | sed 's/^/    /'
        rc=1
    fi
done

if [ $rc -eq 0 ]; then
    echo "OK: no regression of scrubbed secrets."
fi
exit $rc
