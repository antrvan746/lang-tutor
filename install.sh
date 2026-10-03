#!/usr/bin/env bash
# Install the lang-tutor skills (lang-tutor, learn-language) for coding agents.
#
#   ./install.sh                 link both skills for every agent found here
#   ./install.sh claude          ~/.claude/skills        (Claude Code)
#   ./install.sh codex           ~/.agents/skills        (Codex and other Agent Skills readers;
#                                                         also ~/.codex/skills if it exists)
#   ./install.sh coach DIR       make DIR a self-contained coach folder with an AGENTS.md
#                                (any agent that reads AGENTS.md: Codex, Cursor, Gemini CLI, ...)
#   ./install.sh uninstall       remove the links this script created
#
# Skills are symlinked, so `git pull` in this repo updates every agent at once.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$REPO_DIR/skills"
SKILLS=(lang-tutor learn-language)

link_into() {
  local dest="$1" name
  mkdir -p "$dest"
  for name in "${SKILLS[@]}"; do
    local target="$dest/$name"
    if [ -L "$target" ]; then
      ln -sfn "$SKILLS_DIR/$name" "$target"
    elif [ -e "$target" ]; then
      echo "  skip $target: exists and is not a symlink (remove it to let this script manage it)"
      continue
    else
      ln -s "$SKILLS_DIR/$name" "$target"
    fi
    echo "  $target -> $SKILLS_DIR/$name"
  done
}

install_claude() {
  echo "Claude Code:"
  link_into "$HOME/.claude/skills"
  echo "  use: /learn-language init, /learn-language, /lang-tutor <language>"
}

install_codex() {
  echo "Codex / Agent Skills:"
  link_into "$HOME/.agents/skills"
  if [ -d "$HOME/.codex/skills" ]; then link_into "$HOME/.codex/skills"; fi
  cat <<EOF
  use: \$learn-language init, \$learn-language, or ask for a lesson in plain words
  note: Codex's workspace-write sandbox can't write to ~/.lang-tutor. Either run Codex in a
        coach folder (./install.sh coach ~/english-coach), or allow the directory in
        ~/.codex/config.toml:
          [sandbox_workspace_write]
          writable_roots = ["$HOME/.lang-tutor"]
EOF
}

make_coach() {
  local dir="${1:?usage: ./install.sh coach DIR}"
  mkdir -p "$dir"
  dir="$(cd "$dir" && pwd)"
  touch "$dir/.lang-tutor-home"
  if [ -e "$dir/AGENTS.md" ]; then
    echo "  keep existing $dir/AGENTS.md"
  else
    sed "s#{{SKILLS_DIR}}#$SKILLS_DIR#g" "$REPO_DIR/templates/AGENTS.md" >"$dir/AGENTS.md"
    echo "  wrote $dir/AGENTS.md"
  fi
  [ -e "$dir/CLAUDE.md" ] || { ln -s AGENTS.md "$dir/CLAUDE.md"; echo "  linked CLAUDE.md -> AGENTS.md"; }
  echo "Coach folder ready: cd $dir and start your agent, then ask for \"learn-language init\"."
  echo "Learner files will live in $dir/<language>/ (put it in git if you like)."
}

uninstall() {
  local dest name
  for dest in "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.codex/skills"; do
    for name in "${SKILLS[@]}"; do
      if [ -L "$dest/$name" ] && [ "$(readlink "$dest/$name")" = "$SKILLS_DIR/$name" ]; then
        rm "$dest/$name" && echo "  removed $dest/$name"
      fi
    done
  done
  echo "Learner data in ~/.lang-tutor (and any coach folders) was left untouched."
}

case "${1:-auto}" in
  claude) install_claude ;;
  codex | agents) install_codex ;;
  coach) make_coach "${2:-}" ;;
  uninstall) uninstall ;;
  auto)
    found=0
    if [ -d "$HOME/.claude" ] || command -v claude >/dev/null 2>&1; then install_claude; found=1; fi
    if [ -d "$HOME/.codex" ] || [ -d "$HOME/.agents" ] || command -v codex >/dev/null 2>&1; then install_codex; found=1; fi
    [ "$found" = 1 ] || { echo "No agent found. Run ./install.sh claude|codex, or ./install.sh coach DIR."; exit 1; }
    ;;
  -h | --help) awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0" ;;
  *) echo "unknown target: $1 (try --help)" >&2; exit 1 ;;
esac

command -v python3 >/dev/null 2>&1 || echo "warning: python3 not found; learn-language needs Python 3.9+."
