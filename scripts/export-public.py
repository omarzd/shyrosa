#!/usr/bin/env python3
"""Export the allowlisted files into a local checkout of the public repo (shyrosa#94).

    scripts/export-public.py [--from <private repo>] <public checkout>

Reads export/allowlist.txt and every file it names as they stand at the private
repo's HEAD commit, never the working tree. The rulebook loses its ledger
citations on the way, and every other file loses its pointers into the ledger. Then the guard reads every public path and every file
about to be written for the terms in export/private-terms.txt: one hit stops the
run before anything is written, and names the file, the line and the term. A
clean run makes the public checkout hold exactly the allowlisted paths, checks
that what git staged is byte for byte what the guard scanned, and makes one
commit whose message is the private commit's hash alone, as the noreply
identity whatever the machine's git config says, with hooks and machine-wide
attributes off. It never pushes: the push is the manager's word.
"""
import argparse
import os
import posixpath
import re
import subprocess
import sys
import unicodedata

ALLOWLIST = "export/allowlist.txt"
TERMS = "export/private-terms.txt"
RULEBOOK = "WORKFLOW-RULEBOOK.md"
NAME = "omarzd"
EMAIL = "7592333+omarzd@users.noreply.github.com"


def git(cwd, *args, binary=False, env=None, input=None):
    out = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env,
                         input=input).stdout
    return out if binary else out.decode()


# Git settings that would let something other than the scanned bytes reach the
# public commit: a hook editing the message, a clean filter rewriting a file.
QUIET = ("-c", "core.hooksPath=/dev/null", "-c", "core.attributesFile=/dev/null")


def refuse(why):
    sys.exit(f"export: refused, {why}; nothing written")


def parse_allowlist(text):
    """(includes, excludes, renames): folders end in /, renames map source to public name."""
    includes, excludes, renames = [], set(), {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            excludes.add(line[1:].strip())
        elif "->" in line:
            src, dest = (part.strip() for part in line.split("->", 1))
            renames[src] = dest
        else:
            includes.append(line)
    return includes, excludes, renames


def covers(entry, path):
    """An allowlist entry takes in a path: the file itself, or any file under a folder entry."""
    return path == entry or (entry.endswith("/") and path.startswith(entry))


def inside(dest):
    """A public name that stays inside the public checkout and out of any .git, whatever
    its case, since this Mac's file system ignores case."""
    parts = dest.split("/")
    return (bool(dest) and not posixpath.isabs(dest) and posixpath.normpath(dest) == dest
            and ".." not in parts and not any(p.lower() == ".git" for p in parts))


def tree_at(repo, rev):
    """{path: (mode, blob id)} for every entry git tracks at `rev`, whatever its name."""
    tree = {}
    for record in git(repo, "ls-tree", "-r", "-z", rev, binary=True).split(b"\0"):
        if record:
            meta, raw = record.split(b"\t", 1)
            try:
                path = raw.decode("utf-8")
            except UnicodeDecodeError:
                refuse(f"the file name {raw.decode('utf-8', 'backslashreplace')} is not valid UTF-8")
            mode, _, oid = meta.decode().split()
            tree[path] = (mode, oid)
    return tree


def export_set(repo, rev):
    """{public path: (private path, mode, blob id)} for every file the allowlist at `rev` takes in."""
    includes, excludes, renames = parse_allowlist(git(repo, "show", f"{rev}:{ALLOWLIST}"))
    tree = tree_at(repo, rev)
    unmatched = [e for e in includes + list(renames) if not any(covers(e, p) for p in tree)]
    unmatched += ["!" + e for e in sorted(excludes) if not any(covers(e, p) for p in tree)]
    if unmatched:
        refuse(f"the allowlist names paths HEAD does not hold: {', '.join(unmatched)}")
    picked = {}
    for path, (mode, oid) in tree.items():
        if any(covers(exc, path) for exc in excludes):
            continue
        if path in renames:
            dest = renames[path]
        elif any(covers(inc, path) for inc in includes):
            dest = path
        else:
            continue
        if dest in picked:
            refuse(f"{picked[dest][0]} and {path} would both ship as {dest}")
        if mode == "120000":
            refuse(f"{path} is a symlink, which the export does not carry")
        if mode == "160000":
            refuse(f"{path} is a gitlink to another repo, which the export does not carry")
        picked[dest] = (path, mode, oid)
    outside = sorted(d for d in picked if not inside(d))
    if outside:
        refuse(f"a public name would land outside the public checkout: {', '.join(outside)}")
    # Case aside, since this Mac's file system ignores it.
    lowered = [d.lower() for d in picked]
    clash = sorted(d for d in picked if any(e.startswith(d.lower() + "/") for e in lowered))
    if clash:
        refuse(f"a public name is also a folder of other public names: {', '.join(clash)}")
    return picked


# A trailing citation follows an audience tag: ", §7", ", §7, §8", or ", Superseded",
# sometimes wrapped onto a line of its own, which goes with it.
_TRAILING = re.compile(r"(\*\*\((?:D|W|F|M|all)\)\*\*),\s*(?:§\d+(?:,\s*§\d+)*|Superseded)(?=[ \t]*$)",
                       re.MULTILINE)
# Inline: "(..., §8)" keeps its parenthesis, "(ledger §N, sitting gN)" goes whole.
_INLINE = re.compile(r"(?:,\s*§\d+)+\)")
_LEDGER_PAREN = re.compile(r"\s*\(ledger §\d+[^)]*\)")
# The opening paragraph that points at LEDGER.md, and the blank line after it.
_OPENING = re.compile(r"^\*\*Provenance lives in \[`LEDGER\.md`\].*?\n\n", re.MULTILINE | re.DOTALL)


def strip_citations(text):
    """The rulebook as a stranger reads it: no ledger section, no pointer to the ledger."""
    text = _OPENING.sub("", text, count=1)
    text = _TRAILING.sub(r"\1", text)
    text = _INLINE.sub(")", text)
    return _LEDGER_PAREN.sub("", text)


# Ledger mentions in any exported file, which carry no audience tag to key on.
_LEDGER_SECTION = r"(?:ledger|LEDGER) §\d+"
_MENTIONS = [
    # A citation that ends a parenthesis leaves the parenthesis.
    (re.compile(rf",\s*{_LEDGER_SECTION}(?=\))"), ""),
    # A ruling cited with its date keeps the date.
    (re.compile(r"\(rulings ledger §\d+,\s*"), "("),
    # A parenthesis that is only a citation goes whole, with the space before it.
    (re.compile(rf"\s*\({_LEDGER_SECTION}[^)]*\)"), ""),
    (re.compile(rf"\s+and {_LEDGER_SECTION}"), ""),
    (re.compile(r";\s*provenance in the ledger, §\d+"), ""),
    (re.compile(r";\s*why it binds you is\s*\[`LEDGER\.md`\]\(LEDGER\.md\)"), ""),
]


def strip_ledger_mentions(text):
    """`text` without a pointer into the ledger, which does not ship."""
    for pattern, repl in _MENTIONS:
        text = pattern.sub(repl, text)
    return text


# Between two words of a term: any run of whitespace, or line breaks whose next
# lines open with comment or quote markers (#, >, // or more slashes, *), repeated
# with spaces between as in "> > ", so a term wrapped inside a comment or a
# nested quote, across a bare marker line too, still reads as the term.
_SEPARATOR = r"(?:(?:\s*\n[^\S\n]*(?:(?:/{2,}|[#>*])[^\S\n]*)+)+|\s+)"
# Between two parts of a term: a hyphen, an underscore or a Unicode dash (which NFKC
# leaves alone), a _SEPARATOR, both, or nothing, so the term "foo bar" also catches
# "foo-bar", "foo_bar" and "foobar". Parts are what is left of a term split on
# whitespace, hyphens and underscores.
_DASHES = r"\-_‐-―−"
_GAP = rf"[{_DASHES}]?(?:{_SEPARATOR})?"


def load_terms(text):
    """[(term, pattern)]: a term matches wherever it stands, case aside, and each space in
    it matches _SEPARATOR. A "word:" line matches only where no letter or digit touches
    either end of it."""
    terms = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        whole = line.startswith("word:")
        term = line[len("word:"):].strip() if whole else line
        pattern = _GAP.join(re.escape(part) for part in re.split(rf"[\s{_DASHES}]+", visible(term)) if part)
        if whole:
            pattern = rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])"
        terms.append((term, re.compile(pattern, re.IGNORECASE)))
    return terms


# Characters that show nothing on the page but are not format characters (Cf):
# the grapheme joiner, the Hangul fillers and the variation selectors.
_BLANKS = {0x034F, 0x115F, 0x1160, 0x3164, *range(0xFE00, 0xFE10)}


def _drop_invisible(text):
    return "".join(c for c in text
                   if ord(c) not in _BLANKS and unicodedata.category(c) != "Cf")


def visible(text):
    """`text` as it reads: no invisible character, and NFKC applied, so fullwidth and
    other compatibility forms fold to plain letters. Dropped again after NFKC, since
    folding can produce a filler."""
    return _drop_invisible(unicodedata.normalize("NFKC", _drop_invisible(text)))


def scan(name, text, terms):
    """[(name, line, term)] for each match of load_terms' terms anywhere in `text`,
    with the line the match starts on."""
    text = visible(text)
    return [(name, text.count("\n", 0, m.start()) + 1, t)
            for t, p in terms for m in p.finditer(text)]


def shared_history(priv, pub):
    """True when the public checkout is the private repo or holds any commit it holds."""
    if os.path.realpath(priv) == os.path.realpath(pub):
        return True
    # A shared commit brings its ancestors, so it always means a shared root.
    roots = git(pub, "rev-list", "--max-parents=0", "--all").split()
    return any(subprocess.run(["git", "cat-file", "-e", f"{r}^{{commit}}"], cwd=priv,
                              capture_output=True).returncode == 0 for r in roots)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("public", help="a local checkout of the public repo")
    ap.add_argument("--from", dest="private", default=".", help="the private repo (default: here)")
    args = ap.parse_args(argv)
    priv = git(args.private, "rev-parse", "--show-toplevel").strip()
    pub = git(args.public, "rev-parse", "--show-toplevel").strip()
    if subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=pub,
                      capture_output=True).returncode != 0:
        refuse(f"{pub} has no commit; the export goes on top of the public repo's README and LICENSE")
    if shared_history(priv, pub):
        refuse(f"{pub} shares history with the private repo; export only into the public repo")
    # Every untracked file counts, whatever status.showUntrackedFiles says: one left
    # here would be staged with the export and never scanned.
    if git(pub, *QUIET, "status", "--porcelain", "--untracked-files=all"):
        refuse(f"{pub} has uncommitted changes; commit or clear them first")

    head = git(priv, "rev-parse", "HEAD").strip()
    terms = load_terms(git(priv, "show", f"{head}:{TERMS}"))
    if not terms:
        refuse(f"the term list {TERMS} holds no term at {head}")
    files, texts = {}, {}
    for dest, (src, mode, oid) in sorted(export_set(priv, head).items()):
        data = git(priv, "cat-file", "blob", oid, binary=True)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            refuse(f"{src} is not valid UTF-8, so the guard cannot read it")
        stripped = strip_citations(text) if src == RULEBOOK else text
        stripped = strip_ledger_mentions(stripped)
        if stripped != text:
            text, data = stripped, stripped.encode()
        files[dest], texts[dest] = (data, mode), text

    hits = [f"{dest}: private term '{t}' in the path"
            for dest in files for _, _, t in scan(dest, dest, terms)]
    hits += [f"{name}:{line}: private term '{t}'"
             for dest, text in texts.items() for name, line, t in scan(dest, text, terms)]
    if hits:
        for hit in hits:
            print(hit, file=sys.stderr)
        refuse(f"{len(hits)} private term(s) found")

    before = git(pub, "rev-parse", "HEAD").strip()
    try:
        write_and_commit(pub, files, head, before)
    except Exception as failure:
        take_back(pub, before)
        detail = getattr(failure, "stderr", None) or failure
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace").strip()
        refuse(f"a step failed after writing began ({detail}); the public checkout is back as it was")


def write_and_commit(pub, files, head, before):
    """Make the public checkout hold exactly `files`, stage it, check the stage, commit.
    A check that fails takes the checkout back and exits; any other failure raises."""
    root = os.fsencode(pub)
    for old in git(pub, "ls-files", "-z", binary=True).split(b"\0"):
        if old and old.decode("utf-8", "surrogateescape") not in files:
            os.remove(os.path.join(root, old))
            remove_empty_folders(root, os.path.dirname(old))
    for dest, (data, mode) in files.items():
        path = os.path.join(pub, dest)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        os.chmod(path, 0o755 if mode == "100755" else 0o644)
    # Rebuild the index from nothing: on a file system that ignores case, a name
    # whose case changed would otherwise keep its old spelling in the index.
    git(pub, *QUIET, "rm", "-r", "--cached", "-q", "--ignore-unmatch", ".")
    git(pub, *QUIET, "add", "-A")
    mismatch = staged_mismatch(pub, files)
    if mismatch:
        take_back(pub, before)
        refuse(f"what git staged is not what the guard scanned: {', '.join(mismatch)}; "
               "the public checkout is back as it was")
    if not git(pub, *QUIET, "status", "--porcelain", "--untracked-files=all"):
        print(f"export: the public checkout already matches {head}; no commit")
        return
    ident = dict(os.environ, GIT_AUTHOR_NAME=NAME, GIT_AUTHOR_EMAIL=EMAIL,
                 GIT_COMMITTER_NAME=NAME, GIT_COMMITTER_EMAIL=EMAIL)
    git(pub, *QUIET, "commit", "--no-verify", "-q", "-m", head, env=ident)
    message = git(pub, "log", "-1", "--format=%B").strip()
    if message != head:
        take_back(pub, before)
        sys.exit(f"export: the commit's message was not the bare hash {head}, so it was taken "
                 "back; the public checkout is back as it was")
    print(f"export: committed {len(files)} files from {head} in {pub}; not pushed")


def remove_empty_folders(root, folder):
    """Remove `folder` under `root` and each parent above it while they are empty."""
    while folder:
        path = os.path.join(root, folder)
        if not os.path.isdir(path) or os.listdir(path):
            return
        os.rmdir(path)
        folder = os.path.dirname(folder)


def staged_mismatch(pub, files):
    """The public paths where the index differs from the bytes and mode the guard passed:
    a path staged that was never scanned, a scanned path not staged, or a blob a filter
    rewrote on the way in."""
    staged = {}
    for record in git(pub, "ls-files", "-s", "-z", binary=True).split(b"\0"):
        if record:
            meta, raw = record.split(b"\t", 1)
            mode, oid, _ = meta.decode().split()
            staged[raw.decode("utf-8", "surrogateescape")] = (mode, oid)
    wrong = sorted(set(staged) ^ set(files))
    for dest, (data, mode) in files.items():
        if dest in staged:
            oid = git(pub, "hash-object", "--no-filters", "--stdin", input=data).strip()
            if staged[dest] != ("100755" if mode == "100755" else "100644", oid):
                wrong.append(dest)
    return wrong


def take_back(pub, before):
    """Put the public checkout back at `before`, clean. It was clean when the run began,
    so every untracked file now is one this run wrote."""
    git(pub, *QUIET, "reset", "-q", "--hard", before)
    git(pub, *QUIET, "clean", "-fdq")


if __name__ == "__main__":
    main()
