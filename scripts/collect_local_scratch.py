#!/usr/bin/env python3
"""The local-scratch collector — counts markdown stores under `<root>/.scratch/`.

Extracted from one project's board generator; board.py is the frame that calls
it. Counts tickets by their Status: line, the two queue files by open `## N · Title`
headings, and building work by `git worktree list`.

Every markdown file a board links is rendered into a .board/ page (UTF-8, one
anchor per heading) so a click opens a readable page scrolled to the section —
raw file:// markdown renders as mis-encoded plain text and anchors do nothing.
"""
import glob
import os
import re
import subprocess

from md_render import render_file, slug

NEWEST_NAMED = 5  # how many needs-triage tickets the TRIAGE line names

# Capitals are the marker, and the case is load-bearing: a case-blind match hid live
# entries whose titles held the everyday words "moved", "closed" and "Imported".
CLOSED = re.compile(r"SETTLED|SUPERSEDED|DONE|CLOSED|WITHDRAWN|RULED|IMPORTED|VOID|MOVED")
# Every project keeps its worktrees under the repo's own .claude/worktrees/ (g25).
WORKTREES = "/.claude/worktrees/"
# The queue writes its exit as `**Exit:** `<command>``; a bare `Exit:` line reads the same.
EXIT = re.compile(r"^\*{0,2}Exit:\*{0,2}\s*(.*)$")


def first_status(path):
    with open(path, errors="replace") as fh:
        for line in fh:
            if line.startswith("Status:"):
                return line[len("Status:"):].strip()
    return None


def title(path):
    with open(path, errors="replace") as fh:
        for line in fh:
            if line.startswith("# "):
                return line[2:].strip()
    return os.path.basename(path)


def queue_entries(path):
    """(number, title) per open '## N · Title' heading. A queue file is created on first
    park (docs/agents/queues.md), so a missing one is a young project, not an error —
    the crash this guard prevents took down a young project's first Stop hook (2026-08-14)."""
    out = []
    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                m = re.match(r"^## (\S+) · (.*)$", line)
                if m and not CLOSED.search(m.group(2)):
                    out.append((m.group(1), m.group(2).strip()))
    except FileNotFoundError:
        pass
    return out


def grill_entries(path):
    """(number, title, exit) per open '## N · Title' heading, with its Exit: line.
    Missing file: same young-project rule as queue_entries."""
    out = []
    pending = None
    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                m = re.match(r"^## (\S+) · (.*)$", line)
                if m:
                    pending = None if CLOSED.search(m.group(2)) else [m.group(1), m.group(2).strip(), None]
                    if pending:
                        out.append(pending)
                elif pending is not None and EXIT.match(line):
                    pending[2] = EXIT.match(line).group(1).strip().strip("`").strip()
                    pending = None
    except FileNotFoundError:
        pass
    return [(n, t, e) for n, t, e in out]


def page_for(src, outdir, base):
    """Render src into outdir under a collision-safe, visible name; return file:// URL.
    None when src does not exist yet — callers guard their hrefs."""
    if not os.path.exists(src):
        return None
    rel = os.path.relpath(src, base)
    name = re.sub(r"^[.\-]+", "", rel.replace("/", "--")).replace(".md", "") + ".html"
    dest = render_file(src, outdir, name=name, title=os.path.basename(src))
    return "file://" + dest


def entry_href(page_url, num, entry_title):
    if page_url is None:
        return None
    return f"{page_url}#{slug(f'{num} · {entry_title}')}"


def collect(root, cfg):
    tickets = {}
    for p in glob.glob(os.path.join(root, ".scratch/*/issues/*.md")):
        s = first_status(p)
        if s is None:
            continue
        key = s.split()[0].rstrip(":").lower()
        handle = re.sub(r"\.md$", "", os.path.relpath(p, os.path.join(root, ".scratch"))).replace(
            "/issues/", "/"
        )
        tickets.setdefault(key, []).append((handle, title(p), p, os.path.getmtime(p)))

    grills = grill_entries(os.path.join(root, ".scratch/GRILL-QUEUE.md"))
    studio = queue_entries(os.path.join(root, ".scratch/STUDIO-QUEUE.md"))

    wt = subprocess.run(
        ["git", "-C", root, "worktree", "list"], capture_output=True, text=True
    ).stdout
    building = []
    for l in wt.splitlines():
        if WORKTREES not in l:
            continue
        m = re.search(r"\[([^\]]+)\]", l)
        if not m:
            continue
        branch = m.group(1)
        # A worktree that outlives its merge is the normal state between a merge and the
        # next dispatch — nothing is building there (readability ticket 12). Skip branches
        # already ancestors of main; if git cannot answer, keep the row (fail open).
        merged = subprocess.run(
            ["git", "-C", root, "merge-base", "--is-ancestor", branch, "main"],
            capture_output=True,
        ).returncode == 0
        if not merged:
            building.append(l.split()[0].split("/")[-1] + " on " + branch)
    return tickets, grills, studio, building


def build_lines(root, tickets, grills, studio, building, stamp):
    """Board rows: (kind, text, md_ref, href). md_ref shows in BOARD.md; href in HTML."""
    board_pages = os.path.join(root, ".board")
    grill_src = os.path.join(root, ".scratch/GRILL-QUEUE.md")
    studio_src = os.path.join(root, ".scratch/STUDIO-QUEUE.md")
    grill_page = page_for(grill_src, board_pages, root)
    studio_page = page_for(studio_src, board_pages, root)

    def ticket_row(text, path):
        return ("row", text, os.path.relpath(path, root), page_for(path, board_pages, root))

    L = []
    L.append(("h1", f"THE BOARD — counted at {stamp}; nothing here is hand-written", None, None))

    L.append(("h2", "Mandatum? Ik Willen!", None, None))
    pool = sorted(tickets.get("needs-triage", []), key=lambda t: -t[3])
    L.append(("row", f"/triage — {len(pool)} tickets waiting for a sitting", ".scratch",
              "file://" + os.path.join(root, ".scratch")))
    for h, t, p, _ in pool[:NEWEST_NAMED]:
        L.append(ticket_row(f"    to triage: {h} — {t}", p))

    n = len(studio)
    L.append(("h2", f"STUDIO ROUND — {n} brief{'s' if n != 1 else ''} to carry",
              ".scratch/STUDIO-QUEUE.md", studio_page))
    for num, t in studio:
        L.append(("row", f"STUDIO-QUEUE §{num} — {t}", ".scratch/STUDIO-QUEUE.md",
                  entry_href(studio_page, num, t)))

    L.append(("h2", "THE DIRECTOR'S DESK — counted so you can skip it", None, None))
    L.append(("row", f"{len(tickets.get('ready-for-human', []))} tickets at ready-for-human", ".scratch",
              "file://" + os.path.join(root, ".scratch")))
    L.append(("row", f"{len(tickets.get('needs-info', []))} tickets at needs-info", ".scratch",
              "file://" + os.path.join(root, ".scratch")))
    done = sum(len(v) for k, v in tickets.items() if k in ("merged", "done", "promoted", "resolved"))
    closed = sum(len(v) for k, v in tickets.items() if k.startswith("wontfix"))
    L.append(("row", f"{done} tickets merged/done/resolved, {closed} closed as wontfix — history, nothing pending",
              ".scratch", "file://" + os.path.join(root, ".scratch")))

    # The heading counts only entries that carry an Exit: line — an exitless entry is
    # misfiled or waiting on a spec, not offerable, and it still renders below with its
    # flag (readability ticket 12). The heading's wording is not the signal; Exit: is.
    offerable = len([g for g in grills if g[2]])
    L.append(("h2", f"GRILL QUEUE — {offerable} parked; each leaves only through a sitting with you",
              ".scratch/GRILL-QUEUE.md", grill_page))
    for num, t, ex in grills:
        if ex and ex.startswith("/"):
            text = f"{ex} — {t}" if "GRILL-QUEUE" in ex else f"{ex} .scratch/GRILL-QUEUE.md §{num} — {t}"
        elif ex:
            text = f"GRILL-QUEUE §{num} — {t}  [no grill exit: {ex}]"
        else:
            text = f"GRILL-QUEUE §{num} — {t}  [no Exit: line — see docs/agents/queues.md]"
        L.append(("row", text, ".scratch/GRILL-QUEUE.md", entry_href(grill_page, num, t)))

    L.append(("h2", "BUILDING RIGHT NOW — worktrees, not Status: lines", None, None))
    for b in building:
        L.append(("row", b, None, None))
    if not building:
        L.append(("row", "(no worktrees besides main)", None, None))

    L.append(("note", "HOLD <thread> or HOLD ALL — your standing stop-word; pauses the two defaults (drain ready-for-agent; merge on gate PASS)", None, None))
    return L


def build(root, cfg, stamp):
    # The matt-flow extra board retired 2026-08-15 (shyrosa#11): the workflow repo has its
    # own tracker and board now, so one project renders one board.
    tickets, grills, studio, building = collect(root, cfg)
    return {
        "lines": build_lines(root, tickets, grills, studio, building, stamp),
        "html_title": "THE BOARD",
    }
