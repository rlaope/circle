#!/usr/bin/env bash
# verify.sh — single-command acceptance check for circlelib.
#
# Runs the unit suite and a headless smoke run of every example .crl.
# Exit 0 means the working tree is shippable; non-zero means stop.
#
# CI (issue #6) calls this same script. Keep it simple.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1) Unit tests
echo "==> pytest"
pytest -q

# 2) Headless smoke run of every example (recurses into subdirs).
# Use `find` so this stays portable on Bash 3.2 (macOS default) where
# `globstar` and `mapfile` are unavailable.
echo "==> example smoke (--check)"
examples=()
# Skip examples/modules/* — those files are imported by other scenes
# and contain no `scene { ... }` block of their own.
while IFS= read -r line; do
    examples+=("$line")
done < <(find examples -type f -name "*.crl" -not -path "examples/modules/*" | sort)

if [ ${#examples[@]} -eq 0 ]; then
    echo "no examples found under examples/" >&2
    exit 1
fi

for ex in "${examples[@]}"; do
    echo "  $ex"
    python -m circlelib run "$ex" --check
done

echo "==> verify.sh OK"
