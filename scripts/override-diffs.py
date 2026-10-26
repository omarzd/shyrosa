#!/usr/bin/env python3
"""Regenerate the recorded override diffs in docs/overrides/ (shyrosa#107).

    scripts/override-diffs.py [--check] [repo root]

An overlay overrides Matt's skill when upstream/ holds a skill of the same name. For
each one, the record is what `diff -ru upstream/<name> overlay/<name>` reports from the
repo root, with no timestamps in its file headers, so a record changes only when the
text does. Python's difflib writes it, never the diff on PATH: Apple diff and GNU diff
lay the same hunks out differently, and a record must read the same on the Mac and the
box. Lines starting `# ` at the top of a record are a note, kept on rewrite.

With --check it writes nothing, names each record that differs from the diff today,
and exits 1 if any does. The output-style diffs in docs/overrides/ are not overlays
and this script leaves them alone.
"""
import difflib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def overridden(root):
    """Names of the overlays that have a Matt skill of the same name."""
    overlays = os.listdir(os.path.join(root, "overlay"))
    return sorted(n for n in overlays if os.path.isdir(os.path.join(root, "upstream", n))
                  and os.path.isdir(os.path.join(root, "overlay", n)))


def record_path(root, name):
    return os.path.join(root, "docs", "overrides", f"{name}.diff")


def _range(start, length):
    """A hunk range as diff -u writes it: `5,7`, `5` for one line, `4,0` for none."""
    if length == 1:
        return str(start + 1)
    return f"{start + 1 if length else start},{length}"


def _hunks(old, new):
    """Unified hunks with three lines of context, each line ending in a newline."""
    out = []
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for group in matcher.get_grouped_opcodes(3):
        i1, i2, j1, j2 = group[0][1], group[-1][2], group[0][3], group[-1][4]
        out.append(f"@@ -{_range(i1, i2 - i1)} +{_range(j1, j2 - j1)} @@\n")
        for tag, a1, a2, b1, b2 in group:
            if tag == "equal":
                out += [" " + line for line in old[a1:a2]]
                continue
            out += ["-" + line for line in old[a1:a2]]
            out += ["+" + line for line in new[b1:b2]]
    return [line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in out]


def _read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines(True)


def _walk(root, old, new):
    """diff -ru's report for two folders, in its layout, walked in name order."""
    out = []
    old_names = set(os.listdir(os.path.join(root, old)))
    new_names = set(os.listdir(os.path.join(root, new)))
    for entry in sorted(old_names | new_names):
        a, b = f"{old}/{entry}", f"{new}/{entry}"
        full_a, full_b = os.path.join(root, a), os.path.join(root, b)
        if entry not in new_names:
            out.append(f"Only in {old}: {entry}\n")
        elif entry not in old_names:
            out.append(f"Only in {new}: {entry}\n")
        elif os.path.isdir(full_a) and os.path.isdir(full_b):
            out += _walk(root, a, b)
        elif os.path.isfile(full_a) and os.path.isfile(full_b):
            hunks = _hunks(_read_lines(full_a), _read_lines(full_b))
            if hunks:
                out += [f"diff -ru {a} {b}\n", f"--- {a}\n", f"+++ {b}\n", *hunks]
        else:
            sys.exit(f"override-diffs: {a} and {b} are not both files or both folders")
    return out


def current(root, name):
    """The diff today between Matt's skill and our overlay, without timestamps."""
    return "".join(_walk(root, f"upstream/{name}", f"overlay/{name}"))


def split_note(text):
    """(note, diff) for a record's text."""
    lines = text.splitlines(True)
    n = 0
    while n < len(lines) and lines[n].startswith("# "):
        n += 1
    return "".join(lines[:n]), "".join(lines[n:])


def read_record(root, name):
    try:
        with open(record_path(root, name), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def recorded(root, name):
    """The diff part of a record, its note left off."""
    return split_note(read_record(root, name))[1]


def main():
    args = sys.argv[1:]
    check = "--check" in args
    rest = [a for a in args if a != "--check"]
    if len(rest) > 1 or any(a.startswith("-") for a in rest):
        sys.exit(__doc__.split("\n\n")[1])
    root = os.path.abspath(rest[0]) if rest else _ROOT
    stale = []
    for name in overridden(root):
        today = current(root, name)
        note, diff = split_note(read_record(root, name))
        if diff == today:
            continue
        stale.append(name)
        if not check:
            with open(record_path(root, name), "w", encoding="utf-8") as f:
                f.write(note + today)
    if check:
        for name in stale:
            print(f"{name}.diff differs from the overlay today")
        sys.exit(1 if stale else 0)
    for name in stale:
        print(f"wrote docs/overrides/{name}.diff")


if __name__ == "__main__":
    main()
