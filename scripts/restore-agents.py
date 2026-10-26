#!/usr/bin/env python3
"""Resume every agent back into the window it came from after a reboot.

tmux-resurrect brings the sessions, windows, layout and working directories
back, but every restored pane is a bare shell. This reads a resurrect
snapshot, keeps the panes that were running an agent, works out which claude
session belonged to each, and types a plain resume into it. See shyrosa#30 and
shyrosa#31 for the reasoning behind every decision here.

The saved launch line is never replayed. Some of those launches carry a task
prompt, and re-running one would rebuild a finished ticket from scratch. The
resume is built from parts instead: the resolved session id plus the model, the
effort and the permission mode, followed by a fresh instruction to recover any
prior worktree assignment from the resumed history before the next build action.
The recorded directory is not evidence of an assignment. Dropping the saved task
prompt is a property of how the command is built, not a filter someone maintains.

Two kinds of pane are left alone. A name matching no session at all is skipped
and reported, so no agent lands in a window it does not belong to. A pane
already running an agent is skipped, so a by-hand run over a live board never
stacks two agents in one pane.

Everything else resolves. A name shared by several sessions is narrowed by the
pane's recorded directory, and whatever is left, several sessions or the whole
unnarrowed set, resumes into the newest one. Wherever that pick was between
more than one candidate, the run prints that it chose and how many candidates
there were, so a merge is never gated on a silent guess (shyrosa#37).

Usage:
  restore-agents.py [--dry-run] [--session NAME] [--snapshot PATH]

  --dry-run   Print the plan without sending keystrokes.
  --session   Restrict the run to one tmux session; leave the others untouched.
  --snapshot  Read this snapshot file instead of the newest one.

Every run appends timestamps, the snapshot, decisions and errors to
restore-agents.log beside the resurrect snapshots, including during a dry run.
Reports still print to the terminal. XDG_DATA_HOME relocates the snapshot and
log directory together when set.

By default everything it reads lives under HOME: the snapshot under ~/.local/share
and the claude transcripts under ~/.claude. --snapshot can point elsewhere.
Point HOME at a scratch directory and use synthetic snapshots to test without a
test-only flag.
"""
import argparse
import glob
import json
import logging
import os
import shlex
import subprocess
import sys
import time

SHELLS = {"fish", "bash", "zsh", "sh", "dash", "ksh", "tcsh", "csh"}
AGENT_COMMANDS = {"claude", "claude.exe"}


def report(msg):
    logging.info(msg)
    print(msg)


def die(msg):
    logging.error(msg)
    sys.stderr.write("error: %s\n" % msg)
    sys.exit(1)


# -- reading the snapshot -----------------------------------------------------

def resurrect_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
    )
    return os.path.join(base, "tmux", "resurrect")


def newest_snapshot():
    """The `last` pointer resurrect maintains, or the newest dated file if it is
    missing. None when there is no snapshot at all."""
    d = resurrect_dir()
    last = os.path.join(d, "last")
    if os.path.exists(last):
        return last
    dated = sorted(glob.glob(os.path.join(d, "tmux_resurrect_*.txt")))
    return dated[-1] if dated else None


def _strip_leading_colon(field):
    return field[1:] if field.startswith(":") else field


def parse_snapshot(path):
    """Return (panes, window_names). A pane is a dict; window_names maps
    (session, window_index) to the window's name. The pane and window line
    layouts are resurrect's own, read straight off a live snapshot."""
    panes = []
    window_names = {}
    with open(path) as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if parts[0] == "pane" and len(parts) >= 11:
                panes.append({
                    "session": parts[1],
                    "window_index": parts[2],
                    "pane_index": parts[5],
                    "title": parts[6],
                    "cwd": _strip_leading_colon(parts[7]),
                    "current_command": parts[9],
                    "full_command": _strip_leading_colon(parts[10]),
                })
            elif parts[0] == "window" and len(parts) >= 4:
                window_names[(parts[1], parts[2])] = _strip_leading_colon(parts[3])
    return panes, window_names


def agent_name_from_title(title):
    """The session name is the title with its activity marker stripped. Not
    every launch carries a name flag, but the title holds the name in every case
    observed, so the title is the source (shyrosa#30)."""
    return title.lstrip("✳").strip()


def resume_flags(full_command):
    """The model, effort and permission mode from the saved launch, in a fixed
    order. Everything else, the task prompt included, is left behind."""
    toks = full_command.split()
    flags = []
    for name in ("--model", "--effort", "--permission-mode"):
        if name in toks:
            i = toks.index(name)
            if i + 1 < len(toks):
                flags.append("%s %s" % (name, toks[i + 1]))
    return " ".join(flags)


# -- reading the transcripts --------------------------------------------------

def _mtime_of(entry):
    return entry["mtime"]


def scan_transcripts(needed_names):
    """Every claude transcript whose agent name is one we need, as dicts of
    name, cwd, session_id and mtime. Only the header of each file is read, and
    only far enough to find the name and the cwd."""
    base = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    found = []
    for path in glob.glob(os.path.join(base, "*", "*.jsonl")):
        name = None
        cwd = None
        try:
            with open(path) as fh:
                for _ in range(40):
                    line = fh.readline()
                    if not line:
                        break
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    if obj.get("agentName"):
                        name = obj["agentName"]
                    elif name is None and obj.get("customTitle"):
                        name = obj["customTitle"]
                    if cwd is None and obj.get("cwd"):
                        cwd = obj["cwd"]
                    if name is not None and cwd is not None:
                        break
        except OSError as exc:
            logging.warning("could not read transcript %s: %s", path, exc)
            continue
        if name in needed_names:
            found.append({
                "name": name,
                "cwd": cwd,
                "session_id": os.path.splitext(os.path.basename(path))[0],
                "mtime": os.path.getmtime(path),
            })
    return found


def resolve(name, recorded_cwd, transcripts):
    """Resolve a name to one session id, or explain why it cannot.

    Returns (session_id, error, candidate_count): error is None on success or a
    ('no-session',) tuple; candidate_count is None unless resolution had to
    pick between several candidates, in which case it is how many there were.
    A unique name
    resumes regardless of directory with no choosing. A shared name is
    separated by the recorded directory; if that narrows it to exactly one,
    that one resumes, no choosing either. Otherwise the newest wins, from
    whatever the directory left, or from every candidate if the directory left
    nothing, and that pick is reported (shyrosa#37)."""
    candidates = [t for t in transcripts if t["name"] == name]
    if not candidates:
        return None, ("no-session",), None
    if len(candidates) == 1:
        return candidates[0]["session_id"], None, None
    pool = [t for t in candidates if t["cwd"] == recorded_cwd]
    if not pool:
        chosen = max(candidates, key=_mtime_of)
        return chosen["session_id"], None, len(candidates)
    if len(pool) == 1:
        return pool[0]["session_id"], None, None
    chosen = max(pool, key=_mtime_of)
    return chosen["session_id"], None, len(pool)


# -- talking to the live server -----------------------------------------------


def tmux(*args, **kwargs):
    proc = subprocess.run(
        ["tmux", *args], stderr=subprocess.PIPE, text=True, **kwargs,
    )
    if proc.returncode != 0:
        logging.error("tmux %s exited %s: %s", " ".join(args),
                      proc.returncode, proc.stderr.strip())
        if proc.stderr:
            sys.stderr.write(proc.stderr)
    return proc


def require_server():
    if not _which("tmux"):
        die("tmux not found on PATH")
    proc = tmux("list-sessions", stdout=subprocess.DEVNULL)
    if proc.returncode != 0:
        die("no tmux server is reachable. Start a tmux session, or point "
            "TMUX_TMPDIR at the right server.")


def _which(name):
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d and os.access(os.path.join(d, name), os.X_OK):
            return True
    return False


def pane_command(target):
    proc = tmux("display-message", "-p", "-t", target, "#{pane_current_command}",
                stdout=subprocess.PIPE)
    return proc.stdout.strip() if proc.returncode == 0 else None


def return_to_shell(target):
    """Bring a pane holding a pager back to its shell prompt. resurrect restores
    saved scrollback by running a pager that never exits on its own, so the pane
    is sitting in one at the moment the restore runs (shyrosa#31 comment). Send
    q until the shell is back; give up rather than type into a pager."""
    for _ in range(4):
        cmd = pane_command(target)
        if cmd in SHELLS:
            return True
        tmux("send-keys", "-t", target, "q")
        time.sleep(0.5)
    return pane_command(target) in SHELLS


def send_resume(target, command):
    tmux("send-keys", "-t", target, "-l", "--", command)
    time.sleep(0.4)
    tmux("send-keys", "-t", target, "Enter")


# -- the run ------------------------------------------------------------------


class RestoreArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        logging.error(message)
        super().error(message)


def main():
    ap = RestoreArgumentParser(description="Resume every agent back into its pane.")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan without sending keystrokes")
    ap.add_argument("--session", metavar="NAME",
                    help="restrict the run to one tmux session")
    ap.add_argument("--snapshot", metavar="PATH",
                    help="read this snapshot file instead of the newest one")
    args = ap.parse_args()

    logging.info("start restore: dry_run=%s session=%s", args.dry_run, args.session)
    snapshot = args.snapshot if args.snapshot is not None else newest_snapshot()
    if not snapshot:
        die("no resurrect snapshot found under %s" % resurrect_dir())

    logging.info("snapshot: %s (resolved: %s)", snapshot, os.path.realpath(snapshot))
    try:
        panes, window_names = parse_snapshot(snapshot)
    except OSError as exc:
        die("cannot read resurrect snapshot %s: %s" % (snapshot, exc))
    agents = [p for p in panes if p["current_command"] in AGENT_COMMANDS]
    if args.session:
        agents = [p for p in agents if p["session"] == args.session]

    if not agents:
        report("nothing to restore")
        return

    require_server()

    needed = {agent_name_from_title(p["title"]) for p in agents}
    transcripts = scan_transcripts(needed)

    for p in agents:
        window = window_names.get((p["session"], p["window_index"]), p["window_index"])
        target = "%s:%s.%s" % (p["session"], window, p["pane_index"])
        name = agent_name_from_title(p["title"])

        live = pane_command(target)
        if live in AGENT_COMMANDS:
            report("skip %s: already running an agent" % target)
            continue

        session_id, reason, candidate_count = resolve(name, p["cwd"], transcripts)
        if reason is not None:
            report("skip %s: no session named '%s'" % (target, name))
            continue

        if candidate_count is not None:
            report("chose %s: '%s' had %d candidate sessions, resumed the newest" %
                  (target, name, candidate_count))

        flags = resume_flags(p["full_command"])
        command = "claude -r %s%s" % (session_id, (" " + flags) if flags else "")
        prompt = ("Before your next build action, read your full resumed history "
                  "for an assigned worktree. A resume drops the worktree binding. "
                  "If you had an assigned worktree, use EnterWorktree to re-enter "
                  "that same worktree before building. If you were unbound, remain "
                  "unbound; do not create a worktree or bind the main checkout "
                  "just because it is the recorded cwd.")
        command += " " + shlex.quote(prompt)

        if args.dry_run:
            report("plan %s: %s" % (target, command))
            continue

        if not return_to_shell(target):
            report("skip %s: could not return the pane to a shell prompt" % target)
            continue
        send_resume(target, command)
        report("restored %s: %s" % (target, command))


if __name__ == "__main__":
    log_path = os.path.join(resurrect_dir(), "restore-agents.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logging.basicConfig(
        filename=log_path, encoding="utf-8", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    try:
        main()
    except SystemExit as exc:
        logging.info("finish restore: exit=%s", exc.code)
        raise
    except Exception:
        logging.exception("restore failed")
        raise
    else:
        logging.info("finish restore: exit=0")
