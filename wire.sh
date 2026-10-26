#!/usr/bin/env bash
#
# wire.sh — (re)link every skill into ~/.claude/skills so Claude Code loads it,
# and link the fleet settings, status-line script and Unslop style into ~/.claude.
# Codex gets fleet/codex/AGENTS.md and the same successfully linked skills.
#
# Skills come from two folders. overlay/* are ours; upstream/* is the vendored copy of
# Matt's skills. An overlay wins over a Matt skill of the same name, and a Matt skill
# named in not_linked below is vendored but never linked. Both folders are scanned, so a
# new overlay or a vendor bump needs NO edit here. (The human-readable skill
# *count/list* in docs/USING.md and README.md is the only thing you must bump by hand.)
#
# A link already in the skills folder is replaced; a real folder is moved aside
# unless its .pre-fleet name is taken. A link into an old Matt clone (matt-skills
# on the Mac, mattpocock-skills on the box) whose skill is in neither folder, or
# is in not_linked, is removed. Links
# to anywhere else are never touched.
#
# Idempotent: safe to run any number of times.
#
# Portable: derives its own absolute path, so it produces correct links on macOS
# (/Users/…) or Ubuntu (/home/…) alike. Run it after cloning on a new machine.
#
#   ./wire.sh                    # keeps a settings link already made, makes no new one
#   ./wire.sh --link-settings    # also makes the first ~/.claude/settings.json link
#
set -euo pipefail

link_settings=no
for arg in "$@"; do
  case "$arg" in
    --link-settings) link_settings=yes ;;
    *) echo "usage: $0 [--link-settings]" >&2; exit 2 ;;
  esac
done

repo="$(cd "$(dirname "$0")" && pwd -P)"

# ln -s makes a copy, not a link, on Windows outside Developer Mode. A copy would
# drift from the repo unseen, so every link is checked and a copy stops the run.
make_link() {  # <source> <target>
  # -s symlink, -f replace an existing link, -n don't descend into a linked dir.
  # (-n is accepted by both GNU coreutils and BSD/macOS ln.)
  ln -sfn "$1" "$2"
  if [ ! -L "$2" ]; then
    echo "STOP  $2 — not a symlink after ln -s; on Windows, turn on Developer Mode" >&2
    exit 1
  fi
}

# Real targets are preserved once. A taken backup, including a dangling link,
# leaves both paths untouched and lets the caller count the skipped link.
move_aside() {  # <target> <display name>
  local target="$1" label="$2" aside="$1.pre-fleet"
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    if [ -e "$aside" ] || [ -L "$aside" ]; then
      echo "SKIP  $label — real file or folder, and $aside is taken; resolve by hand" >&2
      return 1
    fi
    mv "$target" "$aside" || exit 1
    echo "aside $label -> $label.pre-fleet"
  fi
}

dest="${HOME}/.claude/skills"
mkdir -p "$dest"

# ~/.shyrosa is the fleet's machine-stable address for this repo. Every project's
# CLAUDE.md, output style and board script points through it, so the dev root can be
# named differently on each machine (~/swMac1 here, ~/dev on the Ubuntu box) without
# breaking a single pointer. Created here because this script is what runs per machine.
home_link="${HOME}/.shyrosa"
if [ -e "$home_link" ] && [ ! -L "$home_link" ]; then
  # Moving a checkout we are running from would invalidate every source path.
  home_is_source=no
  if [ -d "$home_link" ]; then
    case "$repo/" in "$(cd "$home_link" && pwd -P)/"*) home_is_source=yes ;; esac
  fi
  if [ "$home_is_source" = yes ]; then
    echo "SKIP  ~/.shyrosa — contains the running checkout; keeping source in place" >&2
  elif [ -e "$home_link.pre-fleet" ] || [ -L "$home_link.pre-fleet" ]; then
    echo "SKIP  ~/.shyrosa — real folder, and $home_link.pre-fleet is taken; resolve by hand" >&2
  else
    mv "$home_link" "$home_link.pre-fleet"
    echo "aside ~/.shyrosa -> ~/.shyrosa.pre-fleet"
  fi
fi
if [ ! -e "$home_link" ] || [ -L "$home_link" ]; then
  make_link "$repo" "$home_link"
  echo "link  ~/.shyrosa -> $repo"
fi

# Vendored but not linked. implement-spec waits on GRILL-QUEUE §52 (shyrosa#103).
not_linked=" implement-spec "

linked=0 skipped=0
# The guarded expansions below also support empty arrays on macOS Bash 3.2.
linked_skills=()
link_skill() {  # <name> <folder under the repo>
  local name="$1" skill_dir="$repo/$2/$1" target="$dest/$1"
  if ! move_aside "$target" "$name"; then
    skipped=$((skipped + 1))
    return
  fi
  make_link "$skill_dir" "$target"
  echo "link  $name -> $skill_dir"
  linked=$((linked + 1))
  linked_skills+=("$name")
}

# An empty or missing folder leaves the glob unexpanded, hence the -d checks.
for dir in "$repo"/overlay/*/; do
  [ -d "$dir" ] || continue
  link_skill "$(basename "$dir")" overlay
done
for dir in "$repo"/upstream/*/; do
  [ -d "$dir" ] || continue
  name="$(basename "$dir")"
  [ -d "$repo/overlay/$name" ] && continue
  case "$not_linked" in *" $name "*) continue ;; esac
  link_skill "$name" upstream
done

# A link into a Matt clone, under either machine's clone name, for a skill neither
# folder holds, or one in not_linked. Matching on the target path leaves every other
# link alone. Move-aside backups are preserved even when they point into a clone.
removed=0
for target in "$dest"/*; do
  [ -L "$target" ] || continue
  name="$(basename "$target")"
  case "$name" in *.pre-fleet) continue ;; esac
  case "$(readlink "$target")" in
    */matt-skills/*|*/mattpocock-skills/*) ;;
    *) continue ;;
  esac
  case "$not_linked" in
    *" $name "*) ;;
    *) if [ -d "$repo/overlay/$name" ] || [ -d "$repo/upstream/$name" ]; then continue; fi ;;
  esac
  rm "$target"
  echo "unlink $name — stale link into a Matt clone"
  removed=$((removed + 1))
done

# The fleet files: one Claude Code setup for every machine (shyrosa#97). Each machine's
# copy is a link into fleet/, so a /config change edits the repo file and shows in
# git status. A real file in the way is renamed aside with a fixed suffix, never
# deleted; if that name is taken too, it is left alone for a human to resolve.
fleet_linked=0 fleet_skipped=0
link_fleet() {  # <path under ~/.claude> <path under the repo>
  local target="${HOME}/.claude/$1" source="$repo/$2"
  mkdir -p "$(dirname "$target")"
  if ! move_aside "$target" "$1"; then
    fleet_skipped=$((fleet_skipped + 1))
    return
  fi
  make_link "$source" "$target"
  echo "link  $1 -> $source"
  fleet_linked=$((fleet_linked + 1))
}
# The settings link turns auto-memory off, so its first link is explicit (#97: the Mac
# links only after its memory pass, #100). Without --link-settings, a link already into
# this repo is kept and anything else at ~/.claude/settings.json is left alone.
settings_note=""
if [ "$link_settings" = yes ] || [ "$(readlink "${HOME}/.claude/settings.json" || true)" = "$repo/fleet/settings.json" ]; then
  link_fleet settings.json fleet/settings.json
else
  settings_note="; settings.json not linked, first link needs --link-settings"
fi
link_fleet statusline-context.py fleet/statusline-context.py
link_fleet output-styles/unslop.md fleet/unslop.md

# Only skills successfully wired above belong to this run's Codex set. In
# particular, a Claude target blocked by an occupied backup is not mirrored.
codex_dest="${HOME}/.codex/skills"
mkdir -p "$codex_dest"
codex_linked=0 codex_skipped=0 codex_removed=0
link_codex() {  # <path under ~/.codex> <absolute source>
  local target="${HOME}/.codex/$1" source="$2"
  if ! move_aside "$target" "~/.codex/$1"; then
    codex_skipped=$((codex_skipped + 1))
    return
  fi
  make_link "$source" "$target"
  echo "link  ~/.codex/$1 -> $source"
  codex_linked=$((codex_linked + 1))
}
link_codex AGENTS.md "$repo/fleet/codex/AGENTS.md"
for name in ${linked_skills[@]+"${linked_skills[@]}"}; do
  link_codex "skills/$name" "$(readlink "$dest/$name")"
done

# Prune only stale links owned by this checkout. Backups and links into any
# other checkout or third-party location belong to the user.
for target in "$codex_dest"/*; do
  [ -L "$target" ] || continue
  name="$(basename "$target")"
  case "$name" in *.pre-fleet) continue ;; esac
  keep=no
  for linked_name in ${linked_skills[@]+"${linked_skills[@]}"}; do
    if [ "$name" = "$linked_name" ]; then keep=yes; break; fi
  done
  [ "$keep" = no ] || continue
  # realpath handles relative links, .., symlinked parents and missing targets.
  # Use the fleet's existing Python runtime rather than platform-specific
  # realpath flags or a second path normalizer written in shell.
  resolved="$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$target")"
  case "$resolved" in "$repo"|"$repo"/*) ;; *) continue ;; esac
  rm "$target"
  echo "unlink ~/.codex/skills/$name — stale link into this repo"
  codex_removed=$((codex_removed + 1))
done

echo "done: ${linked} skills wired, ${skipped} skipped, ${removed} stale clone links removed, into ${dest}; ${fleet_linked} fleet files linked, ${fleet_skipped} skipped; ${codex_linked} codex links, ${codex_skipped} skipped, ${codex_removed} stale codex links removed${settings_note}"
