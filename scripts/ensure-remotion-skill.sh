#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="$ROOT_DIR/.agents/skills/remotion-best-practices"
CLAUDE_LINK="$ROOT_DIR/.claude/skills/remotion-best-practices"

if [[ -f "$SKILL_DIR/SKILL.md" ]]; then
  echo "OK: official Remotion skill is installed at .agents/skills/remotion-best-practices"
  if [[ ! -e "$CLAUDE_LINK/SKILL.md" ]]; then
    mkdir -p "$ROOT_DIR/.claude/skills"
    ln -sfn "../../.agents/skills/remotion-best-practices" "$CLAUDE_LINK"
    echo "OK: recreated Claude Code symlink at .claude/skills/remotion-best-practices"
  fi
  exit 0
fi

if [[ "${1:-}" == "--install" ]]; then
  cd "$ROOT_DIR"
  npx skills add remotion-dev/skills --yes
  exit 0
fi

cat <<'MSG'
Missing official Remotion skill: .agents/skills/remotion-best-practices/SKILL.md

Install it with:
  npx skills add remotion-dev/skills --yes

Agents should ask for permission before running this command because it uses network access.
MSG

exit 1
