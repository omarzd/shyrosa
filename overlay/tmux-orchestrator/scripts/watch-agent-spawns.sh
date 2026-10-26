#!/usr/bin/env bash
# watch-agent-spawns.sh — record who spawns interactive agent sessions.
#
# Answers one question: when a claude/omp/pi session appears that nobody admits
# to starting, what launched it? Logs the new process AND its parent chain, which
# names the culprit directly (a shell, a tmux server, another agent's bash).
#
#   start:  nohup ~/.shyrosa/overlay/tmux-orchestrator/scripts/watch-agent-spawns.sh >/dev/null 2>&1 &
#   read:   tail -f ~/Library/Logs/agent-spawns.log
#   stop:   pkill -f watch-agent-spawns.sh
#
# Ignores one-shot headless runs (`-p` / `--print`) — those are tool calls, not sessions.
#
# The watcher does not survive a reboot, so restart it after one. The log lives in
# ~/Library/Logs rather than /tmp because macOS empties /tmp on boot: the run that
# ends at the reboot is exactly the one you want to read afterwards, and in /tmp it
# is gone before you can.

LOG=${AGENT_SPAWN_LOG:-$HOME/Library/Logs/agent-spawns.log}
INTERVAL=${AGENT_SPAWN_INTERVAL:-3}
seen=" "

echo "[$(date '+%F %T')] watcher started (pid $$, interval ${INTERVAL}s)" >> "$LOG"

while true; do
  while IFS= read -r line; do
    pid=$(awk '{print $1}' <<< "$line")
    [[ -z $pid ]] && continue
    [[ $seen == *" $pid "* ]] && continue
    seen+="$pid "

    ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    pcmd=$(ps -o command= -p "$ppid" 2>/dev/null | cut -c1-200)
    gpid=$(ps -o ppid= -p "$ppid" 2>/dev/null | tr -d ' ')
    gcmd=$(ps -o command= -p "$gpid" 2>/dev/null | cut -c1-200)
    started=$(ps -o lstart= -p "$pid" 2>/dev/null)
    pane=$(tmux list-panes -a -F '#{pane_pid} #{session_name}:#{window_index} #{window_name}' 2>/dev/null \
             | awk -v p="$ppid" '$1==p {print $2" "$3}')

    {
      echo "── NEW AGENT $(date '+%F %T')"
      echo "   pid   : $pid   started: $started"
      echo "   cmd   : $(ps -o command= -p "$pid" 2>/dev/null | cut -c1-220)"
      echo "   parent: [$ppid] $pcmd"
      echo "   gparent:[$gpid] $gcmd"
      [[ -n $pane ]] && echo "   pane  : $pane"
    } >> "$LOG"
  done < <(ps -eo pid,command 2>/dev/null \
             | grep -E '(^| |/|\()claude(\.exe)?($| )|bin/omp($| )|bin/pi($| )' \
             | grep -vE 'grep|watch-agent-spawns|Claude\.app|Helper|zsh -c| -p | --print')

  sleep "$INTERVAL"
done
