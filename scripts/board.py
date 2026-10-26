#!/usr/bin/env python3
"""The board frame — one frame for the fleet; each project brings a collector.

The project root arrives as argv[1]; the project's facts come from
`<root>/.claude/fleet.json`. Its `tracker` key picks the collector module
(`local-scratch` -> collect_local_scratch, `github-issues` -> collect_github_issues),
which counts that project's stores and returns board rows. The frame owns what the
collectors share: the time stamp, writing the board pair (the html path comes from
fleet.json's `board_html` — `<project>-board.html` by convention, relative to the root,
see fleet_config — and the .md rides beside it), the board-changed flag, and writing any extra boards a collector
builds. Runs on a Stop hook after every turn in a project.
Sections and order are the manager's rulings: wayfinder-fleet-readability tickets
02 (shape), 03 (block format), 08 (trigger, freshness, home). Only this script may
state freshness.
"""
import html
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet_config  # noqa: E402


def md_text(lines):
    out = []
    for kind, text, md_ref, _ in lines:
        if kind == "h1":
            out.append(f"# {text}\n")
        elif kind == "h2":
            out.append(f"\n## {text}\n")
        elif kind == "row":
            out.append(f"- {text}" + (f"  ({md_ref})" if md_ref else ""))
        elif kind == "note":
            out.append(f"\n{text}")
    return "\n".join(out) + "\n"


def strip_stamp(text):
    return "\n".join(l for l in text.splitlines() if "counted at " not in l)


def record_board_changed(root, md_path, new_md):
    """The changed verdict only the generator may state (tickets 03/08, amended 2026-08-09)."""
    try:
        old = open(md_path, errors="replace").read()
    except FileNotFoundError:
        old = ""
    changed = strip_stamp(old) != strip_stamp(new_md)
    os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
    # The flag is sticky (WORKFLOW-QUEUE §28): a render only ever raises it, and only the
    # check lowers it — after a passing message actually carried the board line. Without
    # this, an agent regenerating the board to verify its own work consumes the change,
    # and a bounced message re-runs this script and consumes it again: a turn that truly
    # changed the board could then never legally say so.
    flag_path = os.path.join(root, ".claude/board-changed")
    if not changed:
        try:
            changed = open(flag_path).read().strip() == "1"
        except FileNotFoundError:
            pass
    with open(flag_path, "w") as fh:
        fh.write("1" if changed else "0")


def write_html(lines, dest, page_title):
    body = []
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    for kind, text, _, href in lines:
        t = html.escape(text)
        if kind == "h1":
            body.append(f"<h1>{t}</h1>")
        elif kind == "h2":
            close_list()
            body.append(f'<h2><a href="{html.escape(href)}">{t}</a></h2>' if href else f"<h2>{t}</h2>")
            body.append("<ul>")
            in_list = True
        elif kind == "row":
            body.append(f'<li><a href="{html.escape(href)}">{t}</a></li>' if href else f"<li>{t}</li>")
        elif kind == "note":
            close_list()
            body.append(f"<p class='hold'>{t}</p>")
    doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{page_title}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 60rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
  h1 {{ font-size: 1.2rem; border-bottom: 2px solid currentColor; padding-bottom: .4rem; }}
  h2 {{ font-size: 1rem; margin-top: 1.6rem; }}
  a {{ color: inherit; }}
  .hold {{ margin-top: 2rem; font-weight: 600; border-top: 1px solid currentColor; padding-top: .6rem; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #1a1a1a; color: #ddd; }} }}
</style></head><body>
{os.linesep.join(body)}
</body></html>
"""
    with open(dest, "w") as fh:
        fh.write(doc)


def main():
    # No stdin read here. The Stop hook already gives this script `< /dev/null`, so it never
    # sees the hook's JSON, and a blocking read hangs any agent that runs the board by hand.
    root, cfg = fleet_config.load(sys.argv[1])
    tracker = cfg["tracker"]
    if tracker == "local-scratch":
        import collect_local_scratch as collector
    elif tracker == "github-issues":
        import collect_github_issues as collector
    else:
        print(f"board.py: unknown tracker '{tracker}' in {root}/.claude/fleet.json", file=sys.stderr)
        return 1
    stamp = datetime.now().strftime("%H:%M")
    board = collector.build(root, cfg, stamp)
    text = md_text(board["lines"])
    md_path = cfg["board_html"][:-len(".html")] + ".md" if cfg["board_html"].endswith(".html") else cfg["board_html"] + ".md"
    record_board_changed(root, md_path, text)
    with open(md_path, "w") as fh:
        fh.write(text)
    write_html(board["lines"], cfg["board_html"], board["html_title"])
    for extra in board.get("extra_boards", []):
        with open(extra["md_path"], "w") as fh:
            fh.write(md_text(extra["lines"]))
        write_html(extra["lines"], extra["html_path"], extra["html_title"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
