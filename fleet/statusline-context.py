#!/usr/bin/env python3
"""Claude Code status line: context usage, model, effort, project, pane, branch.

Runs locally on every render. Its output goes to the terminal UI only, never
into the conversation transcript, so the assistant never sees it. That is the
point: check context privately.

Reads the status-line JSON payload on stdin. Field names are probed rather than
assumed, so a rename upstream degrades to a blank segment instead of a crash. The
render is headless, with stdin the payload and stdout a pipe, so anything needing
the terminal, such as the pane's own window name, is asked of tmux, not a tty.
"""
import json
import os
import re
import subprocess
import sys


def dig(d, *paths, default=None):
    """First matching dotted path wins."""
    for path in paths:
        cur = d
        ok = True
        for key in path.split("."):
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and cur is not None:
            return cur
    return default


def human(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "?"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


RESET, DIM, GREEN, YELLOW, RED, CYAN = (
    "\033[0m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[36m",
)

_EFFORT_EVENT = re.compile(r"Set effort level to (\w+)")


def most_recent_effort_event(text):
    """The level named by the last `/effort` command in a transcript tail.

    The command writes `Set effort level to <level> ...` to its own stdout, and
    that line is the only place the name `ultracode` appears. The per-turn dial
    reports ultracode as plain `xhigh`. Tail order is chronological, so the last
    match is the newest change. Returns the level string, or None if the tail
    holds no `/effort` event.
    """
    matches = _EFFORT_EVENT.findall(text or "")
    return matches[-1] if matches else None


def read_tail(path, max_bytes=65536):
    """The last `max_bytes` of a file as text, or "" if it can't be read.

    Bounded so the per-render cost is one small read regardless of transcript
    size. Decodes leniently, so a split multibyte char at the cut is replaced
    rather than fatal, and the effort marker is plain ASCII anyway.
    """
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            return f.read().decode("utf-8", "replace")
    except Exception:
        return ""


def _launch_is_ultracode(parent_cmd):
    """True when the parent process was launched with `--effort ultracode`."""
    if not parent_cmd:
        return False
    argv = parent_cmd.split()
    argv0 = os.path.basename(argv[0]) if argv else ""
    return "claude" in argv0 and (
        "--effort ultracode" in parent_cmd or "--effort=ultracode" in parent_cmd
    )


def resolve_effort_name(payload, tail_text, parent_cmd):
    """The effort name to show, the live dial promoted to `ultracode` when so.

    The dial `effort.level` is live and authoritative for the level. Ultracode
    dials to plain `xhigh`, so it needs a second signal. Newest wins, so the
    order runs from most recent action to least:

      1. The most recent `/effort` event in the transcript tail. A mid-run
         switch is a dated action, so it settles the question outright, whether
         it turned ultracode on or off.
      2. Failing any transcript event, this is a launch-set session. A payload
         marker, if the harness ever grows one, comes first here.
      3. Then the launch line itself, `--effort ultracode` on the parent.

    Ultracode is only ever asserted on a positive signal, so plain `xhigh` is
    never promoted by mistake.
    """
    effort = dig(payload, "effort.level")
    if effort != "xhigh":
        return effort
    event = most_recent_effort_event(tail_text)
    if event == "ultracode":
        return "ultracode"
    if event is not None:
        return "xhigh"  # newest mid-run set was to something other than ultracode
    if dig(payload, "effort.ultracode", "effort.dynamic_workflows", "ultracode"):
        return "ultracode"
    return "ultracode" if _launch_is_ultracode(parent_cmd) else "xhigh"


def resolve_project(payload, common_dir):
    """The project name: the git repo, not the worktree folder.

    Prefer the payload's repo name, which is worktree-invariant and comes from
    the remote. Else fall back to the git common dir. From a worktree it points
    at the main checkout's `.git`, so the project is its parent's basename.
    Never the last segment of `cwd`, which for a worker is the worktree, not the
    project.
    """
    name = dig(payload, "workspace.repo.name")
    if isinstance(name, str) and name:
        return name
    if common_dir:
        return os.path.basename(os.path.dirname(common_dir)) or None
    return None


def match_window_by_tty(tty, panes_output):
    """The tmux window name whose pane owns `tty`, from `list-panes` output.

    The fallback for when `$TMUX_PANE` didn't survive into the render: match the
    parent process's tty (`ttys031`) against each pane's tty (`/dev/ttys031`) by
    suffix. Window names may contain spaces, so split off only the tty.
    """
    if not tty or tty == "??":
        return None
    for row in (panes_output or "").splitlines():
        parts = row.split(None, 1)
        if len(parts) == 2 and parts[0].endswith(tty):
            return parts[1].strip() or None
    return None


def _run(argv, timeout=1):
    """A trimmed subprocess stdout, or "" on any failure."""
    try:
        return subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout
        ).stdout.strip()
    except Exception:
        return ""


def render_window(env):
    """The current tmux window name, or None when not resolvable / not in tmux.

    Asks tmux directly since the render is headless. `$TMUX_PANE` survives into
    the render (verified), so it is the primary key; the parent-tty match is the
    fallback. Outside tmux, both the guard and the failed calls yield None, so
    the segment is dropped rather than printed empty.
    """
    if not env.get("TMUX") and not env.get("TMUX_PANE"):
        return None
    target = env.get("TMUX_PANE", "")
    if target:
        name = _run(
            ["tmux", "display-message", "-p", "-t", target, "#{window_name}"]
        )
        if name:
            return name
    tty = _run(["ps", "-o", "tty=", "-p", str(os.getppid())])
    panes = _run(["tmux", "list-panes", "-a", "-F", "#{pane_tty} #{window_name}"])
    return match_window_by_tty(tty, panes)


def render_project(payload, cwd):
    """The project name, running git only when the payload lacks the repo name."""
    if dig(payload, "workspace.repo.name"):
        return resolve_project(payload, "")
    common_dir = _run(
        ["git", "-C", str(cwd), "rev-parse", "--path-format=absolute",
         "--git-common-dir"]
    )
    return resolve_project(payload, common_dir)


def render_effort(payload):
    """The effort name for display, reading the transcript tail and launch line."""
    if dig(payload, "effort.level") != "xhigh":
        return dig(payload, "effort.level")
    tail = read_tail(dig(payload, "transcript_path", default="") or "")
    parent = _run(["ps", "-o", "command=", "-p", str(os.getppid())])
    return resolve_effort_name(payload, tail, parent)


def build_segments(payload, env):
    segments = []

    pct = dig(payload, "context_window.used_percentage", "context.used_percentage")
    used = dig(
        payload,
        "context_window.total_input_tokens",
        "context_window.current_usage.input_tokens",
        "context.used_tokens",
    )
    size = dig(payload, "context_window.context_window_size", "context.size")
    if pct is None and used and size:
        try:
            pct = (int(used) / int(size)) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            pct = None

    if pct is not None:
        try:
            p = float(pct)
        except (TypeError, ValueError):
            p = 0.0
        colour = GREEN if p < 50 else (YELLOW if p < 75 else RED)
        filled = min(10, max(0, round(p / 10)))
        bar = "█" * filled + "░" * (10 - filled)
        label = f"{colour}{bar} {p:.0f}%{RESET}"
        if used and size:
            try:
                left = int(size) - int(used)
                label += f" {DIM}({human(left)} left){RESET}"
            except (TypeError, ValueError):
                pass
        segments.append(label)
    else:
        segments.append(f"{DIM}ctx n/a{RESET}")

    def push_cyan(value):
        if isinstance(value, str) and value:
            segments.append(f"{CYAN}{value}{RESET}")

    push_cyan(dig(payload, "model.display_name", "model.name", "model"))
    push_cyan(render_effort(payload))

    # Location cluster: which pane am I in, and which project. The manager gets
    # lost between project windows, so these answer it at a glance.
    cwd = dig(payload, "workspace.current_dir", "cwd", default=os.getcwd())
    push_cyan(render_window(env))
    push_cyan(render_project(payload, cwd))

    branch = _run(["git", "-C", str(cwd), "rev-parse", "--abbrev-ref", "HEAD"])
    if branch:
        segments.append(f"{DIM}{branch}{RESET}")

    return segments


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    segments = build_segments(payload, os.environ)
    print(f" {DIM}·{RESET} ".join(segments))


if __name__ == "__main__":
    main()
