#!/usr/bin/env bash
# Verify all LifeLine OpenClaw SKILL.md files exist and have valid frontmatter.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SKILLS_DIR="$ROOT/features/agent-autonomous/workspace/skills"

EXPECTED=(
  lifeline-ops
  lifeline-monitor
  lifeline-tube
  lifeline-roads
  lifeline-parking-charging
  lifeline-equity
  lifeline-spatial
  lifeline-channel-reply
  lifeline-data-analysis
  lifeline-programming
  lifeline-feedback-loop
)

fail=0
for name in "${EXPECTED[@]}"; do
  f="$SKILLS_DIR/$name/SKILL.md"
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f"
    fail=1
    continue
  fi
  if ! grep -q '^name: '"$name" "$f"; then
    echo "BAD frontmatter name in $f"
    fail=1
  fi
  if ! grep -q '^description:' "$f"; then
    echo "MISSING description in $f"
    fail=1
  fi
  echo "OK: $name"
done

[[ -f "$SKILLS_DIR/README.md" ]] && echo "OK: skills/README.md" || { echo "MISSING: skills/README.md"; fail=1; }

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "All ${#EXPECTED[@]} LifeLine skills validated."
