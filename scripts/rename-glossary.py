#!/usr/bin/env python3
"""Rename the domain glossary from CONTEXT.md to GLOSSARY.md in every project (shyrosa#105).

    scripts/rename-glossary.py <dev root>

Matt's skills from v1.3.0 on read GLOSSARY.md and no longer the old name. For each
project directly under the dev root that has a root CONTEXT.md, the script renames
every tracked CONTEXT.md, CONTEXT-MAP.md and CONTEXT-FORMAT.md to GLOSSARY.md,
GLOSSARY-MAP.md and GLOSSARY-FORMAT.md, wherever it sits, and rewrites every mention
of the three old names, and the pointer `CONTEXT §` (to `GLOSSARY §`), in the project's
tracked text files, records included, and in the targets of its tracked symlinks. Then
it makes one commit with the identity git resolves for that repo, with hooks off.

It skips, and lists, a folder that is not a git repo, a Matt clone (a remote on
mattpocock's GitHub), a project whose tree is not clean, one not on a branch, one
whose root CONTEXT.md git does not track, one where a new name is already taken,
and one for which git cannot resolve an author or committer identity. Identity follows
repo config, then global config, with the same environment overrides as a normal commit.
A step that fails puts the project back as it was. A vendored upstream/ folder inside a project
is never touched. A project already renamed has no root CONTEXT.md, so a second run
finds nothing to do. It never pushes.

This file and its tests name the old files on purpose.
"""
import os
import re
import subprocess
import sys

NEW_NAMES = {"CONTEXT.md": "GLOSSARY.md", "CONTEXT-MAP.md": "GLOSSARY-MAP.md",
             "CONTEXT-FORMAT.md": "GLOSSARY-FORMAT.md"}
# An old name standing alone: BOUNDED-CONTEXT.md and CONTEXT.mdx are other files.
MENTION = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, NEW_NAMES)) + r")(?!\w)")
# A bare pointer into the glossary, as in "CONTEXT §4" (shyrosa#121). Bare CONTEXT elsewhere stays.
SECTION = re.compile(r"(?<![\w-])CONTEXT (?=§)")
MATT = re.compile(r"[/:]mattpocock/")
REGULAR = ("100644", "100755")
QUIET = ("-c", "core.hooksPath=/dev/null", "-c", "core.attributesFile=/dev/null")


class Skip(Exception):
    """A project the run leaves as it found it, with the reason it prints."""


def git(cwd, *args, env=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          env=env).stdout.decode("utf-8", "surrogateescape")


def editable(path, mode):
    """A tracked file or symlink outside any vendored upstream/ folder."""
    return mode in REGULAR + ("120000",) and "upstream" not in path.split("/")[:-1]


def rewrite_mentions(text):
    return SECTION.sub("GLOSSARY ", MENTION.sub(lambda m: NEW_NAMES[m.group(1)], text))


def is_matt_clone(project):
    try:
        urls = git(project, "config", "--get-regexp", r"^remote\..*\.url$")
    except subprocess.CalledProcessError:
        return False
    return any(MATT.search(line) for line in urls.splitlines())


def check_may_change(project):
    """Raise Skip unless the run may change `project`."""
    try:
        top = git(project, "rev-parse", "--show-toplevel").strip()
    except subprocess.CalledProcessError:
        raise Skip("not a git repo")
    if os.path.realpath(top) != os.path.realpath(project):
        raise Skip(f"not its own git repo, it sits inside {top}")
    if is_matt_clone(project):
        raise Skip("a Matt clone")
    if git(project, "status", "--porcelain", "--untracked-files=all"):
        raise Skip("tree not clean")
    try:
        git(project, "symbolic-ref", "-q", "HEAD")
    except subprocess.CalledProcessError:
        raise Skip("not on a branch")


def tracked(project):
    """{path: mode} for every entry git tracks."""
    entries = {}
    for record in git(project, "ls-files", "-s", "-z").split("\0"):
        if record:
            meta, path = record.split("\t", 1)
            entries[path] = meta.split()[0]
    return entries


def plan_renames(project, entries):
    """[(old path, new path)] for each tracked glossary file outside upstream/."""
    if entries.get("CONTEXT.md") not in REGULAR:
        raise Skip("its root CONTEXT.md is not a file git tracks")
    renames = []
    for path, mode in sorted(entries.items()):
        base = os.path.basename(path)
        if base in NEW_NAMES and mode in REGULAR and editable(path, mode):
            renames.append((path, os.path.join(os.path.dirname(path), NEW_NAMES[base])))
    taken = [new for _, new in renames
             if new in entries or os.path.lexists(os.path.join(project, new))]
    if taken:
        raise Skip(f"{', '.join(taken)} already exists")
    return renames


def rewrite(project, entries):
    """Rewrite old names in each tracked text file and symlink target outside upstream/;
    the paths changed."""
    changed = []
    for path, mode in sorted(entries.items()):
        if not editable(path, mode):
            continue
        full = os.path.join(project, path)
        if mode == "120000":
            target = os.readlink(full)
            if rewrite_mentions(target) != target:
                os.remove(full)
                os.symlink(rewrite_mentions(target), full)
                changed.append(path)
            continue
        with open(full, "rb") as f:
            data = f.read()
        # Binary means it fails to decode as UTF-8. A NUL inside a string literal still decodes.
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        updated = rewrite_mentions(text)
        if updated != text:
            with open(full, "wb") as f:
                f.write(updated.encode("utf-8"))
            changed.append(path)
    return changed


def take_back(project, before):
    """Put `project` back at `before`. Its tree was clean when the run began, so every
    untracked file now is one this run wrote."""
    git(project, *QUIET, "reset", "-q", "--hard", before)
    git(project, *QUIET, "clean", "-fdq")


def migrate_project(project):
    """Rename and rewrite `project` and commit it once; return the lines to print."""
    check_may_change(project)
    entries = tracked(project)
    renames = plan_renames(project, entries)
    try:
        for kind in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
            git(project, "var", kind)
    except subprocess.CalledProcessError:
        raise Skip("no resolvable git identity; configure user.name and user.email")
    before = git(project, "rev-parse", "HEAD").strip()
    try:
        for old, new in renames:
            git(project, *QUIET, "mv", "--", old, new)
        changed = rewrite(project, tracked(project))
        git(project, *QUIET, "add", "-A")
        message = ("Rename the domain glossary CONTEXT.md to GLOSSARY.md\n\n"
                   "Matt's skills read GLOSSARY.md from v1.3.0 on. CONTEXT-MAP.md and\n"
                   "CONTEXT-FORMAT.md take their GLOSSARY names too, and every mention of\n"
                   "the old names is rewritten. So is every pointer \"CONTEXT §\", which\n"
                   "becomes \"GLOSSARY §\".\n")
        git(project, *QUIET, "commit", "--no-verify", "-q", "-m", message)
    except Exception as failure:
        take_back(project, before)
        detail = getattr(failure, "stderr", None) or failure
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace").strip()
        raise Skip(f"a step failed ({detail}), put back as it was")
    sha = git(project, "rev-parse", "--short", "HEAD").strip()
    lines = [f"renamed {old} -> {new}" for old, new in renames]
    lines += [f"rewrote {path}" for path in changed]
    lines.append(f"committed {sha}")
    return lines


def main():
    if len(sys.argv) != 2 or sys.argv[1].startswith("-"):
        sys.exit(__doc__.split("\n\n")[1])
    root = os.path.abspath(sys.argv[1])
    if not os.path.isdir(root):
        sys.exit(f"rename-glossary: {root} is not a folder")
    done, skipped = [], []
    for name in sorted(os.listdir(root)):
        project = os.path.join(root, name)
        # Listed, not os.path.isfile: this Mac's file system would take context.md for it.
        if not os.path.isdir(project) or "CONTEXT.md" not in os.listdir(project):
            continue
        try:
            lines = migrate_project(project)
        except Skip as why:
            skipped.append(name)
            print(f"{name}: skipped, {why}")
            continue
        done.append(name)
        for line in lines:
            print(f"{name}: {line}")
    if done:
        print(f"rename-glossary: renamed {len(done)} project(s), skipped {len(skipped)}; not pushed")
    else:
        print(f"rename-glossary: nothing to do, skipped {len(skipped)}")


if __name__ == "__main__":
    main()
