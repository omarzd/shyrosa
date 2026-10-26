#!/usr/bin/env python3
"""The github-issues collector — counts GitHub Issues by label, via gh.

Extracted from one project's board generator; board.py is the frame that calls
it. The stores are GitHub Issues (by label, for the repo the project's fleet.json
names), the two queue files at the repo root, and `git worktree list`. A failed
count prints as a failure, never as a zero — a board that cannot count says so.

Queue files the board links are rendered into .board/ pages (UTF-8, one anchor per
heading) so a click opens a readable page scrolled to the section.
"""
import json
import os
import re
import subprocess

from md_render import render_file, slug

NEWEST_NAMED = 5

# g28 (2026-09-01): the disk that got eaten was Docker's, not the
# director's context. 26G real sat under a 300G apparent sparse file the day this landed;
# 40G sits above that baseline and below the 55G that hurt, so the row stays quiet until
# it matters.
DOCKER_RAW_PATH = os.path.expanduser(
    "~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"
)
DOCKER_RAW_THRESHOLD = 40 * 1024**3


def docker_disk_row(path=DOCKER_RAW_PATH, threshold=DOCKER_RAW_THRESHOLD):
    """One board row once Docker.raw's real block size passes threshold; None otherwise.

    st_blocks * 512 is real disk use regardless of the filesystem's own block size — a
    sparse Docker.raw can carry a huge st_size while holding almost nothing. Missing
    file (docker absent or wiped) and any stat failure both mean silence, not an error.
    """
    try:
        real_bytes = os.stat(path).st_blocks * 512
    except OSError:
        return None
    if real_bytes < threshold:
        return None
    gb = real_bytes / 1024**3
    return ("row", f"Docker.raw is at {gb:.1f} GB on disk: `docker system prune` is yours to run", None, None)


CLOSED = re.compile(r"SETTLED|SUPERSEDED|DONE|CLOSED|WITHDRAWN|RULED|IMPORTED|VOID|MOVED", re.I)
# Every project keeps its worktrees under the repo's own .claude/worktrees/ (g25).
WORKTREES = "/.claude/worktrees/"
# The queue writes its exit as `**Exit:** `<command>``; a bare `Exit:` line reads the same.
EXIT = re.compile(r"^\*{0,2}Exit:\*{0,2}\s*(.*)$")


def page_for(src, root):
    # A queue file is created on first park (docs/agents/queues.md), so a missing one is a
    # normal state for a young project, not an error.
    if not os.path.exists(src):
        return None
    rel = os.path.relpath(src, root)
    name = re.sub(r"^[.\-]+", "", rel.replace("/", "--")).replace(".md", "") + ".html"
    return "file://" + render_file(src, os.path.join(root, ".board"), name=name, title=os.path.basename(src))


def queue_entries(path):
    """(title) per open '## ' heading; this collector's queue entries are unnumbered."""
    out = []
    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                m = re.match(r"^## (.*)$", line)
                if m and not CLOSED.search(m.group(1)):
                    out.append(m.group(1).strip())
    except FileNotFoundError:
        pass
    return out


def grill_entries(path):
    """(title, exit) per open '## ' heading, with its Exit: line."""
    out = []
    pending = None
    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                m = re.match(r"^## (.*)$", line)
                if m:
                    pending = None if CLOSED.search(m.group(1)) else [m.group(1).strip(), None]
                    if pending:
                        out.append(pending)
                elif pending is not None and EXIT.match(line):
                    pending[1] = EXIT.match(line).group(1).strip().strip("`").strip()
                    pending = None
    except FileNotFoundError:
        pass
    return [(t, e) for t, e in out]


def gh_issues(root):
    """Open issues bucketed by label, or None when gh cannot count."""
    p = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--limit", "200",
         "--json", "number,title,labels,updatedAt"],
        capture_output=True, text=True, cwd=root, timeout=30,
    )
    if p.returncode != 0:
        return None
    issues = json.loads(p.stdout)
    by_label = {}
    for i in issues:
        for lb in i.get("labels", []):
            by_label.setdefault(lb["name"], []).append(i)
    return by_label


def collect(root, cfg):
    try:
        by_label = gh_issues(root)
    except Exception:
        by_label = None
    grills = grill_entries(os.path.join(root, "GRILL-QUEUE.md"))
    studio = queue_entries(os.path.join(root, "STUDIO-QUEUE.md"))
    wt = subprocess.run(["git", "-C", root, "worktree", "list"],
                        capture_output=True, text=True).stdout
    building = []
    for l in wt.splitlines():
        if WORKTREES not in l:
            continue
        m = re.search(r"\[([^\]]+)\]", l)
        if not m:
            continue
        branch = m.group(1)
        # Skip branches already merged into main — a worktree outliving its merge is not
        # building (readability ticket 12). If git cannot answer, keep the row (fail open).
        merged = subprocess.run(
            ["git", "-C", root, "merge-base", "--is-ancestor", branch, "main"],
            capture_output=True,
        ).returncode == 0
        if not merged:
            building.append(l.split()[0].split("/")[-1] + " on " + branch)
    return by_label, grills, studio, building


def build_lines(root, cfg, by_label, grills, studio, building, stamp):
    """Board rows: (kind, text, md_ref, href)."""
    issues_url = f"https://github.com/{cfg['github_repo']}/issues"
    grill_page = page_for(os.path.join(root, "GRILL-QUEUE.md"), root)
    studio_page = page_for(os.path.join(root, "STUDIO-QUEUE.md"), root)
    L = []
    title = cfg.get("board_title", f"THE {os.path.basename(root).upper()} BOARD")
    L.append(("h1", f"{title} — counted at {stamp}; nothing here is hand-written", None, None))

    L.append(("h2", "Mandatum? Ik Willen!", None, None))
    if by_label is None:
        L.append(("row", "COUNT FAILED — gh could not list the issues; the tracker sections on this board are stale", issues_url, issues_url))
    else:
        pool = sorted(by_label.get("needs-triage", []), key=lambda i: i.get("updatedAt", ""), reverse=True)
        u = issues_url + "?q=is%3Aopen+label%3Aneeds-triage"
        L.append(("row", f"/triage — {len(pool)} tickets waiting for a sitting", u, u))
        for i in pool[:NEWEST_NAMED]:
            u = issues_url + f"/{i['number']}"
            L.append(("row", f"    to triage: #{i['number']} — {i['title']}", u, u))
        # Open wayfinder maps — each row is a paste-ready sitting line (shyrosa#11).
        for i in sorted(by_label.get("wayfinder:map", []), key=lambda i: i["number"]):
            u = issues_url + f"/{i['number']}"
            L.append(("row", f"/wayfinder {u} — {i['title']}", u, u))

    n = len(studio)
    L.append(("h2", f"STUDIO ROUND — {n} brief{'s' if n != 1 else ''} to carry", "STUDIO-QUEUE.md", studio_page))
    for t in studio:
        L.append(("row", f"STUDIO-QUEUE — {t}", "STUDIO-QUEUE.md", f"{studio_page}#{slug(t)}" if studio_page else None))

    L.append(("h2", "THE DIRECTOR'S DESK — counted so you can skip it", None, None))
    if by_label is None:
        L.append(("row", "COUNT FAILED — see above", issues_url, issues_url))
    else:
        u = issues_url + "?q=is%3Aopen+label%3Aready-for-human"
        L.append(("row", f"{len(by_label.get('ready-for-human', []))} tickets at ready-for-human", u, u))
        u = issues_url + "?q=is%3Aopen+label%3Aneeds-info"
        L.append(("row", f"{len(by_label.get('needs-info', []))} tickets at needs-info", u, u))
        u = issues_url + "?q=is%3Aopen+label%3Aready-for-agent"
        L.append(("row", f"{len(by_label.get('ready-for-agent', []))} tickets at ready-for-agent, draining by default", u, u))

    L.append(("h2", f"GRILL QUEUE — {len(grills)} parked; each leaves only through a sitting with you", "GRILL-QUEUE.md", grill_page))
    for t, ex in grills:
        if ex and ex.startswith("/"):
            text = f"{ex} — {t}" if "GRILL-QUEUE" in ex else f"{ex} GRILL-QUEUE.md — {t}"
        elif ex:
            text = f"GRILL-QUEUE — {t}  [no grill exit: {ex}]"
        else:
            text = f"GRILL-QUEUE — {t}  [no Exit: line — see docs/agents/queues.md]"
        L.append(("row", text, "GRILL-QUEUE.md", f"{grill_page}#{slug(t)}" if grill_page else None))

    L.append(("h2", "BUILDING RIGHT NOW — worktrees, not labels", None, None))
    for b in building:
        L.append(("row", b, None, None))
    if not building:
        L.append(("row", "(no worktrees besides main)", None, None))

    docker_row = docker_disk_row()
    if docker_row:
        L.append(("h2", "DISK", None, None))
        L.append(docker_row)

    L.append(("note", "HOLD <thread> or HOLD ALL — your standing stop-word; pauses the two defaults (drain ready-for-agent; merge on gate PASS)", None, None))
    return L


def build(root, cfg, stamp):
    by_label, grills, studio, building = collect(root, cfg)
    return {
        "lines": build_lines(root, cfg, by_label, grills, studio, building, stamp),
        "html_title": cfg.get("board_title", f"THE {os.path.basename(root).upper()} BOARD"),
    }
