#!/usr/bin/env bash
# Package the runflow-ad-creative skill into a .skill bundle (a zip with
# .skill extension) that Claude Cowork and claude.ai web accept under
# "+ → Upload a skill".
#
# Usage:
#   bash scripts/package.sh                 # writes runflow-ad-creative.skill to repo root
#   bash scripts/package.sh /some/where.skill
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/runflow-ad-creative.skill}"
SKILL_DIR="$ROOT/skills/runflow-ad-creative"

if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
  echo "error: $SKILL_DIR/SKILL.md not found — wrong cwd?" >&2
  exit 1
fi

rm -f "$OUT"
(
  cd "$SKILL_DIR"
  # The bundle is a zip with .skill extension. Exclude Python bytecode and
  # the per-skill .gitignore (it's repo plumbing, not skill content).
  zip -r -q "$OUT" . \
    -x "__pycache__/*" "*.pyc" ".gitignore" "*.DS_Store"
)

echo "wrote $OUT"
echo "size:  $(du -h "$OUT" | cut -f1)"
echo
echo "Upload via: + (next to message box) → Upload a skill"
