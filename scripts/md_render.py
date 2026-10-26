"""Minimal markdown -> HTML for the boards' linked pages.

Every file a board links is rendered to a .board/ sibling so a click opens a real
page: UTF-8 declared (raw file:// text lets the browser guess Latin-1 and garble
paragraph marks), one anchor per heading (a raw .md scrolls nowhere), readable
styling. Both projects' board generators import this one module — a shared
renderer cannot drift the way two copies would.
"""
import html as _html
import os
import re


def slug(text):
    t = re.sub(r"[`*_]", "", text.strip().lower())
    t = re.sub(r"[^a-z0-9؀-ۿ]+", "-", t)
    return t.strip("-") or "section"


def _inline(s):
    s = _html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_to_html(md, title):
    out = []
    in_list = in_table = in_code = False

    def close():
        nonlocal in_list, in_table
        if in_list:
            out.append("</ul>")
            in_list = False
        if in_table:
            out.append("</table>")
            in_table = False

    for l in md.splitlines():
        if l.startswith("```"):
            close()
            in_code = not in_code
            out.append("<pre>" if in_code else "</pre>")
            continue
        if in_code:
            out.append(_html.escape(l))
            continue
        m = re.match(r"^(#{1,4}) (.*)$", l)
        if m:
            close()
            n = len(m.group(1))
            out.append(f'<h{n} id="{slug(m.group(2))}">{_inline(m.group(2))}</h{n}>')
            continue
        if re.match(r"^-{3,}\s*$", l):
            close()
            out.append("<hr>")
            continue
        if l.startswith("|"):
            if not in_table:
                close()
                out.append("<table>")
                in_table = True
            if re.match(r"^\|[\s\-|:]+\|$", l):
                continue
            cells = [c.strip() for c in l.strip("|").split("|")]
            out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
            continue
        m = re.match(r"^\s*[-*] (.*)$", l)
        if m:
            if in_table:
                out.append("</table>")
                in_table = False
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(m.group(1))}</li>")
            continue
        if not l.strip():
            close()
            continue
        close()
        out.append(f"<p>{_inline(l)}</p>")
    close()
    body = os.linesep.join(out)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{_html.escape(title)}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 60rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.55; }}
  code {{ background: rgba(127,127,127,.15); padding: .1em .3em; border-radius: 3px; }}
  table {{ border-collapse: collapse; }} td {{ border: 1px solid #8884; padding: .3em .6em; }}
  h2 {{ margin-top: 1.8em; border-bottom: 1px solid #8884; padding-bottom: .2em; }}
  :target {{ background: rgba(255,220,0,.25); }}
  a {{ color: inherit; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #1a1a1a; color: #ddd; }} }}
</style></head><body>
{body}
</body></html>
"""


def render_file(src, outdir, name=None, title=None):
    """Render one markdown file into outdir; returns the destination path."""
    os.makedirs(outdir, exist_ok=True)
    if name is None:
        name = os.path.splitext(os.path.basename(src))[0] + ".html"
    dest = os.path.join(outdir, name)
    md = open(src, errors="replace").read()
    with open(dest, "w") as fh:
        fh.write(md_to_html(md, title or os.path.basename(src)))
    return dest
