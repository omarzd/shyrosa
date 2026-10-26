#!/usr/bin/env bash
# tmux orchestrator helper for multi-agent Pi workflows.
# Lets you list panes, send a prompt to a Pi (or any) process in another pane,
# and read that pane's output back.
#
# Usage:
#   orchestrate.sh panes [session]
#       List every pane in [session] with index, title, command, pid.
#       Name the session: `panes myapp` reads any session on the server,
#       which is how a fleet-level foreman sees another project's board. A wrong
#       name fails loudly. Bare `panes` reads the current session and so needs
#       TMUX set to say which one that is.
#
#   orchestrate.sh send <target> <text...>
#       Type <text> into <target> pane and press Enter.
#       Name the session in <target>: a pane id ("%3"), a window id ("@5"), a
#       session id ("$1"), or "session:win.pane". A bare window name needs TMUX
#       set to resolve which session it belongs to.
#
#   orchestrate.sh send-raw <target> <text...>
#       Type <text> WITHOUT pressing Enter (useful for multi-step input).
#
#   orchestrate.sh enter <target>
#       Send a bare Enter to <target>.
#
#   orchestrate.sh read <target> [lines]
#       Print the last [lines] (default 200) of <target> pane's visible+scrollback.
#
#   orchestrate.sh wait-idle <target> [seconds] [poll]
#       Block until <target> pane output stops changing for [seconds] (default 3),
#       polling every [poll] secs (default 1), max ~120s. Useful after `send`.
#
#   orchestrate.sh capture <target>
#       Dump the entire scrollback of <target> (alias: read with full history).
#
# Notes:
# - Name the session in every target: a pane id (%3), a window id (@5), a
#   session id ($1), or session:window (myapp:worker-1). Those resolve
#   without knowing which session you sit in, so they work in any shell. A bare
#   window name needs TMUX set to say which session it belongs to.
# - "current session" = the session of the pane this script runs in.
set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

# The two questions that actually gate a call: is tmux installed, and is a
# server answering? This replaces the old $TMUX test. An agent's Bash calls do
# not reliably carry $TMUX even from a pane plainly inside tmux, so its absence
# is no evidence the caller is outside a session.
require_server() {
  command -v tmux >/dev/null 2>&1 || die "tmux not found on PATH"
  tmux list-sessions >/dev/null 2>&1 \
    || die "no tmux server is reachable. Start a tmux session, or point TMUX_TMPDIR at the right server."
}

# A target names its own session, and so resolves in any shell, when it is a
# pane id, a window id, a session id, or carries a session before a colon. A
# bare window name does not: it needs TMUX set to say which session it means.
target_names_session() {
  case "$1" in
    %*|@*|\$*) return 0 ;;                          # pane id, window id, session id
    *:*) [ -n "${1%%:*}" ] && return 0 || return 1 ;;  # session:window (non-empty prefix)
    *) return 1 ;;                                  # bare window name
  esac
}

require_target() {
  local t="$1"
  target_names_session "$t" && return 0
  [ -n "${TMUX:-}" ] && return 0
  die "target '$t' is a bare name and needs the current session to resolve. With TMUX unset, name the session: a pane id (%3), a window id (@5), a session id (\$1), or session:window (myapp:worker-1)."
}

cur_session() { tmux display-message -p '#S'; }

cmd_panes() {
  local sess
  if [ -n "${1:-}" ]; then
    sess="$1"
    tmux has-session -t "=$sess" 2>/dev/null || die "no session named '$sess' on this server"
  else
    [ -n "${TMUX:-}" ] || die "bare 'panes' needs the current session to resolve. With TMUX unset, name the session: panes <session>."
    sess=$(cur_session)
  fi
  echo "Session: $sess"
  printf '%-8s %-18s %-15s %-8s %s\n' "PANE" "WINDOW" "COMMAND" "PID" "TITLE"
  tmux list-panes -s -t "$sess" \
    -F '#{pane_id}|#{window_index}:#{window_name}|#{pane_current_command}|#{pane_pid}|#{pane_title}' \
  | while IFS='|' read -r pid win cmd ppid title; do
      printf '%-8s %-18s %-15s %-8s %s\n' "$pid" "$win" "$cmd" "$ppid" "$title"
    done
}

pane_hash() {
  tmux capture-pane -p -t "$1" -S -30 | { md5 2>/dev/null || md5sum; } | awk '{print $1}'
}

# Whatever form the caller typed, ask tmux which session, window and pane it
# actually names, so the closing line can say where the message landed rather
# than repeat a bare name that could resolve to another project's pane. The
# window name, not its index, is the fleet's address for a pane (WORKFLOW-VOCAB.md).
resolve_target() {
  tmux display-message -p -t "$1" '#{session_name}:#{window_name}.#{pane_index}'
}

# A pager can react to Enter just like a shell or agent. Check who will receive
# the keystrokes before typing anything; pane movement alone cannot prove that.
require_input_receiver() {
  local target="$1" command
  command=$(tmux display-message -p -t "$target" '#{pane_current_command}')
  case "$command" in
    fish|bash|zsh|sh|dash|ksh|tcsh|csh|claude|claude.exe|codex|pi) return 0 ;;
    *) die "refusing input to '$target': foreground process '$command' is neither a shell nor an agent CLI" ;;
  esac
}

cmd_send() {
  local target="${1:?target required}"; shift
  local text="$*"
  [ -n "$text" ] || die "no text to send"
  require_input_receiver "$target"
  tmux send-keys -t "$target" -l -- "$text"
  # TUI prompt editors treat a fast burst as a paste; an Enter riding the same
  # burst gets swallowed as a pasted newline instead of submitting. Pause first.
  sleep 0.4
  # Verify submission: the pane must react to Enter. A pane that stays
  # pixel-identical received nothing actionable.
  local pre post
  pre=$(pane_hash "$target")
  tmux send-keys -t "$target" Enter
  sleep 1; post=$(pane_hash "$target")
  if [ "$post" = "$pre" ]; then
    tmux send-keys -t "$target" Enter   # retry once
    sleep 1; post=$(pane_hash "$target")
  fi
  if [ "$post" = "$pre" ]; then
    echo "WARNING: $target static after Enter x2 - prompt may be UNSUBMITTED. Pane tail:" >&2
    tmux capture-pane -p -t "$target" -S -15 >&2
    return 1
  fi
  echo "submitted to $(resolve_target "$target"): $text"
}

cmd_send_raw() {
  local target="${1:?target required}"; shift
  local text="$*"
  require_input_receiver "$target"
  tmux send-keys -t "$target" -l -- "$text"
  echo "sent (no enter) to $target: $text"
}

cmd_enter() {
  local target="${1:?target required}"
  require_input_receiver "$target"
  tmux send-keys -t "$target" Enter
  echo "enter -> $target"
}

cmd_read() {
  local target="${1:?target required}"
  local lines="${2:-200}"
  tmux capture-pane -p -t "$target" -S "-${lines}"
}

cmd_capture() {
  local target="${1:?target required}"
  tmux capture-pane -p -t "$target" -S -
}

cmd_wait_idle() {
  local target="${1:?target required}"
  local stable="${2:-3}"
  local poll="${3:-1}"
  local last="" same=0 elapsed=0 max=120
  while [ "$elapsed" -lt "$max" ]; do
    local now; now=$(tmux capture-pane -p -t "$target" -S -50 | md5 2>/dev/null || tmux capture-pane -p -t "$target" -S -50 | md5sum)
    if [ "$now" = "$last" ]; then
      same=$((same + poll))
      if [ "$same" -ge "$stable" ]; then
        echo "idle: $target stable for ${stable}s"
        return 0
      fi
    else
      same=0
    fi
    last="$now"
    sleep "$poll"
    elapsed=$((elapsed + poll))
  done
  echo "timeout: $target still changing after ${max}s" >&2
  return 1
}

sub="${1:-}"; shift || true
case "$sub" in
  ""|-h|--help) sed -n '2,41p' "$0"; exit 0 ;;
esac
require_server
case "$sub" in
  panes) cmd_panes "$@" ;;
  send|send-raw|enter|read|capture|wait-idle)
    [ -n "${1:-}" ] || die "target required"
    require_target "$1"
    case "$sub" in
      send)      cmd_send "$@" ;;
      send-raw)  cmd_send_raw "$@" ;;
      enter)     cmd_enter "$@" ;;
      read)      cmd_read "$@" ;;
      capture)   cmd_capture "$@" ;;
      wait-idle) cmd_wait_idle "$@" ;;
    esac
    ;;
  *) die "unknown subcommand: $sub (try --help)" ;;
esac
