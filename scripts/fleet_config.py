"""A project's fleet facts, read from `<root>/.claude/fleet.json` for the machine it runs on.

One copy for the board and the MANDATUM check, so both name the same root and the same board.
The wiring a project tracks holds no machine path (shyrosa#87): the Stop hook passes
`$CLAUDE_PROJECT_DIR`, and `board_html` is relative to the project root, so one tracked file
works under `~/swMac1` on the Mac and `~/swvu1` on the box. An absolute `board_html` still
works, for projects that stay on one machine.
"""
import json
import os
import subprocess


def main_checkout(root):
    """The main checkout's root when `root` is a linked worktree, else `root` unchanged.

    A session in a worktree gets the worktree as its project dir. The board and its flag
    have always lived in the main checkout, when the hook named it by absolute path, so a
    worktree session keeps writing there instead of dirtying its own tree.
    """
    try:
        out = subprocess.run(
            ["git", "-C", root, "rev-parse", "--git-dir", "--git-common-dir"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return root
    lines = out.stdout.splitlines()
    if out.returncode != 0 or len(lines) != 2:
        return root
    git_dir, common = (os.path.abspath(os.path.join(root, p)) for p in lines)
    if git_dir == common:
        return root
    return os.path.dirname(common)


def load(root):
    """(root, cfg): the root the board lives under, and fleet.json with `board_html` absolute."""
    root = main_checkout(root)
    with open(os.path.join(root, ".claude", "fleet.json")) as fh:
        cfg = json.load(fh)
    cfg["board_html"] = os.path.join(root, cfg["board_html"])
    return root, cfg
