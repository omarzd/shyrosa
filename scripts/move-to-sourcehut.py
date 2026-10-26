#!/usr/bin/env python3
"""Move every private repo, and every project never pushed, to a private SourceHut repo (shyrosa#115).

    scripts/move-to-sourcehut.py <dev root> [--push]

For each project directly under the dev root, the script reads its origin remote:

- on GitHub under omarzd and private, or no remote at all: it moves;
- on GitHub under omarzd and public: it stays on GitHub, skipped;
- anyone else's, on GitHub or SourceHut: a clone, skipped;
- already ~omarzd's SourceHut repo: moved before, only the steps still missing run.

A moving project gets a SourceHut repo made private through `hut`, named
`<name>-private` when a public `omarzd/<name>` is on GitHub and plain `<name>`
otherwise, where <name> is the project's folder. A repo another machine already made
is used, not made again, but only when it is private and empty or shares history with
the project. The project's own git config commits as the SourceHut
address, origin points at SourceHut, and the GitHub remote stays under the name
`github` for the tracker, since tickets stay in GitHub Issues.

Making the SourceHut repo is the one network write that runs without --push; no
git push runs without it. With it, every branch and tag goes to
SourceHut, and then the private GitHub copy gets one README line saying where the
code lives, committed as the noreply address on top of GitHub's default branch, in
README.md, else README, else a new README.md. The local tree never sees that line. The script prints what it did and skipped. Each
step checks first, so a second run changes nothing.

It skips, and lists, a folder that is not its own git repo, a project with remotes
but no origin, an unmoved one that already has a remote named github, a moved one
whose github remote is not a private omarzd repo, one whose origin is on neither
GitHub nor SourceHut, one GitHub cannot answer for, and one where a git, hut or gh
call fails or the command is missing. A skip ends that project's turn, never the run.

The SourceHut address is read from docs/agents/fleet-references.md, the first
<address> under its SourceHut heading, because this file is exported and that one
is not.
"""
import os
import re
import subprocess
import sys
import tempfile

REFERENCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                          "docs", "agents", "fleet-references.md")
OWNER = "omarzd"
NOREPLY = "7592333+omarzd@users.noreply.github.com"
SOURCEHUT = f"git@git.sr.ht:~{OWNER}/"
GITHUB_REMOTE = "github"
GITHUB_URL = re.compile(
    r"^(?:git@github\.com:|ssh://github\.com/|https://github\.com/)([^/]+)/([^/]+?)(?:\.git)?/?$")
SOURCEHUT_URL = re.compile(
    r"^(?:git@git\.sr\.ht:|ssh://git\.sr\.ht/|https://git\.sr\.ht/)~([^/]+)/([^/]+?)(?:\.git)?/?$")
QUIET = ("-c", "core.hooksPath=/dev/null")
README_NAMES = ("README.md", "README")
TEXT_MODES = ("100644", "100755")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class Skip(Exception):
    """A project the run leaves as it found it, with the reason it prints."""


def without_userinfo(text):
    """Remove URL userinfo, including in command diagnostics, without changing SCP remotes."""
    return re.sub(r"([A-Za-z][A-Za-z0-9+.-]*://)[^/\s?#]*@", r"\1", text)


def sourcehut_address(references):
    """The first <address> in the section of `references` whose heading names SourceHut."""
    section = False
    for line in references.splitlines():
        if line.startswith("## "):
            section = "SourceHut" in line
        elif section:
            found = re.search(r"<([^<>\s]+@[^<>\s]+)>", line)
            if found:
                return found.group(1)
    return None


def run(cwd, *cmd, env=None, check=True, input=None, text=True):
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=text, env=env,
                          input=input)


def git(cwd, *args, env=None):
    return run(cwd, "git", *args, env=env).stdout.strip()


def config(project, key):
    """`key` from the project's own config, or None."""
    return run(project, "git", "config", "--local", "--get", key, check=False).stdout.strip() or None


def github_visibility(project, repo):
    """PUBLIC, PRIVATE or INTERNAL for `omarzd/<repo>`, or None when GitHub has no such
    repo. Raise Skip when gh cannot say, since a guess could misname a repo for good."""
    r = run(project, "gh", "repo", "view", f"{OWNER}/{repo}", "--json", "visibility",
            "-q", ".visibility", check=False)
    if r.returncode == 0:
        return r.stdout.strip().upper()
    if "Could not resolve to a Repository" in r.stderr:
        return None
    raise Skip(f"gh could not read {OWNER}/{repo} ({r.stderr.strip()})")


def sourcehut_name(project):
    """The SourceHut repo name for an unmoved project: `-private` only beside a public twin."""
    name = os.path.basename(project)
    return f"{name}-private" if github_visibility(project, name) == "PUBLIC" else name


def plan(project):
    """(SourceHut name, GitHub URL or None, moved already) for `project`, or raise Skip."""
    try:
        top = git(project, "rev-parse", "--show-toplevel")
    except subprocess.CalledProcessError:
        raise Skip("not a git repo")
    if os.path.realpath(top) != os.path.realpath(project):
        raise Skip(f"not its own git repo, it sits inside {top}")
    origin = config(project, "remote.origin.url")
    if origin is None:
        if git(project, "remote"):
            raise Skip("it has remotes but no origin")
        return sourcehut_name(project), None, False
    hut = SOURCEHUT_URL.match(without_userinfo(origin))
    if hut:
        if hut.group(1) != OWNER:
            raise Skip("a clone of someone else's repo")
        github = config(project, f"remote.{GITHUB_REMOTE}.url")
        if github:
            check_github_remote(project, github)
        return hut.group(2), github, True
    hub = GITHUB_URL.match(without_userinfo(origin))
    if not hub:
        raise Skip(f"origin {origin} is on neither GitHub nor SourceHut")
    if hub.group(1) != OWNER:
        raise Skip("a clone of someone else's repo")
    visibility = github_visibility(project, hub.group(2))
    if visibility is None:
        raise Skip(f"origin {OWNER}/{hub.group(2)} is not on GitHub")
    if visibility == "PUBLIC":
        raise Skip("public, stays on GitHub")
    if config(project, f"remote.{GITHUB_REMOTE}.url") is not None:
        raise Skip(f"it already has a remote named {GITHUB_REMOTE}")
    return sourcehut_name(project), origin, False


def check_github_remote(project, url):
    """Raise Skip unless the github remote of a moved project is a private omarzd repo,
    the only kind the README line may be pushed to."""
    hub = GITHUB_URL.match(without_userinfo(url))
    if not hub or hub.group(1) != OWNER:
        raise Skip(f"its {GITHUB_REMOTE} remote {url} is not {OWNER}'s")
    if github_visibility(project, hub.group(2)) != "PRIVATE":
        raise Skip(f"its {GITHUB_REMOTE} remote {OWNER}/{hub.group(2)} is not private")


def check_existing_repo(project, name, shown):
    """Raise Skip unless the SourceHut repo `hut git show` described in `shown` is
    private and either empty or sharing history with the project."""
    lines = ANSI.sub("", shown).splitlines()
    if f"{name} (private)" not in lines:
        raise Skip(f"SourceHut repo {name} is not private")
    url = SOURCEHUT + name
    heads = [line.split("\t") for line in git(project, "ls-remote", "--heads", url).splitlines()]
    if not heads:
        return
    ours = git(project, "for-each-ref", "--format=%(objectname)", "refs/heads").splitlines()
    objects = os.path.join(git(project, "rev-parse", "--path-format=absolute",
                               "--git-common-dir"), "objects")
    # The remote's history lands in a scratch repo that borrows the project's objects,
    # so the project is left as it was found whatever the answer.
    with tempfile.TemporaryDirectory() as scratch:
        git(scratch, "init", "-q", "--bare")
        with open(os.path.join(scratch, "objects", "info", "alternates"), "w") as f:
            f.write(objects + "\n")
        git(scratch, *QUIET, "fetch", "-q", "--no-write-fetch-head", url,
            *(ref for _, ref in heads))
        for theirs, _ in heads:
            for mine in ours:
                if run(scratch, "git", "merge-base", theirs, mine, check=False).returncode == 0:
                    return
    raise Skip(f"SourceHut repo {name} shares no history with it")


def make_repo(project, name):
    """Make the private SourceHut repo unless it exists; the lines to print."""
    shown = run(project, "hut", "git", "show", name, check=False)
    if shown.returncode == 0:
        check_existing_repo(project, name, shown.stdout)
        return [f"SourceHut repo {name} already there"]
    r = run(project, "hut", "git", "create", name, "--visibility", "private", check=False)
    if r.returncode != 0:
        raise Skip(f"hut could not make {name} ({r.stderr.strip()})")
    return [f"made private SourceHut repo {name}"]


def set_config(project, name, github, address):
    """Point the remotes and the commit identity at SourceHut; the lines to print."""
    lines = []
    url = SOURCEHUT + name
    if github and config(project, f"remote.{GITHUB_REMOTE}.url") is None:
        git(project, "remote", "rename", "origin", GITHUB_REMOTE)
        lines.append(f"kept GitHub as remote {GITHUB_REMOTE}")
    if config(project, "remote.origin.url") is None:
        git(project, "remote", "add", "origin", url)
        lines.append(f"origin -> {url}")
    for key, value in (("user.name", OWNER), ("user.email", address)):
        if config(project, key) != value:
            git(project, "config", "--local", key, value)
            lines.append(f"{key} = {value}")
    return lines


def unpushed(project):
    """Local branches and tags that origin lacks or holds at another commit."""
    local = git(project, "for-each-ref", "--format=%(refname) %(objectname)",
                "refs/heads", "refs/tags").splitlines()
    remote = {}
    for line in git(project, "ls-remote", "origin").splitlines():
        sha, ref = line.split("\t")
        remote[ref] = sha
    pairs = (entry.split() for entry in local)
    return [ref for ref, sha in pairs if remote.get(ref) != sha]


def push_to_sourcehut(project):
    refs = unpushed(project)
    if not refs:
        return []
    git(project, *QUIET, "push", "-q", "-u", "origin", "--all")
    git(project, *QUIET, "push", "-q", "origin", "--tags")
    return [f"pushed {len(refs)} branch(es) and tag(s) to SourceHut"]


def readme_line(name):
    return (f"This repo's code moved to SourceHut, at https://git.sr.ht/~{OWNER}/{name}. "
            "Its Issues stay here.")


def github_readme(project, tip):
    """(path, mode, text) of the README at `tip`: README.md, else README, else a new
    README.md. Raise Skip when the one found is not a UTF-8 text file."""
    root = {}
    for entry in git(project, "ls-tree", "-z", tip).split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            root[path] = meta.split()
    for readme in README_NAMES:
        if readme not in root:
            continue
        mode, kind, sha = root[readme]
        if kind != "blob" or mode not in TEXT_MODES:
            raise Skip(f"{readme} on GitHub is not a plain file")
        data = run(project, "git", "cat-file", "blob", sha, text=False).stdout
        try:
            return readme, mode, data.decode("utf-8")
        except UnicodeDecodeError:
            raise Skip(f"{readme} on GitHub is not UTF-8 text")
    return README_NAMES[0], TEXT_MODES[0], ""


def mark_github_copy(project, name):
    """Commit the README line on top of the GitHub copy's default branch and push it.
    The commit is built from git objects alone, so the local tree never changes."""
    head = git(project, "ls-remote", "--symref", GITHUB_REMOTE, "HEAD")
    branch = next((line.split()[1] for line in head.splitlines() if line.startswith("ref:")), None)
    if branch is None:
        return ["GitHub copy has no default branch, no README line"]
    tip = git(project, "ls-remote", GITHUB_REMOTE, branch).split()[0]
    git(project, *QUIET, "fetch", "-q", "--no-write-fetch-head", GITHUB_REMOTE, branch)
    readme, mode, text = github_readme(project, tip)
    if readme_line(name) in text.splitlines():
        return []
    if text and not text.endswith("\n"):
        text += "\n"
    text += ("\n" if text else "") + readme_line(name) + "\n"
    blob = run(project, "git", "hash-object", "-w", "--stdin", input=text).stdout.strip()
    with tempfile.TemporaryDirectory() as scratch:
        index = dict(os.environ, GIT_INDEX_FILE=os.path.join(scratch, "index"))
        git(project, "read-tree", tip, env=index)
        git(project, "update-index", "--add", "--cacheinfo", f"{mode},{blob},{readme}", env=index)
        tree = git(project, "write-tree", env=index)
    ident = dict(os.environ, GIT_AUTHOR_NAME=OWNER, GIT_AUTHOR_EMAIL=NOREPLY,
                 GIT_COMMITTER_NAME=OWNER, GIT_COMMITTER_EMAIL=NOREPLY)
    commit = git(project, "commit-tree", tree, "-p", tip, "-m",
                 "Point at SourceHut, where the code lives now", env=ident)
    git(project, *QUIET, "push", "-q", GITHUB_REMOTE, f"{commit}:{branch}")
    return [f"added the SourceHut line to {readme} on GitHub"]


def move_project(project, push, address):
    """Move `project` as far as `push` allows; the lines to print, empty when nothing changed."""
    name, github, moved = plan(project)
    lines = [] if moved else make_repo(project, name)
    lines += set_config(project, name, github, address)
    if not push:
        if unpushed(project):
            lines.append(WAITING)
        return lines
    lines += push_to_sourcehut(project)
    if github:
        lines += mark_github_copy(project, name)
    return lines


WAITING = "not pushed, waits for --push"


def failure_reason(failure):
    """The skip reason for a command that failed or is not installed."""
    if isinstance(failure, FileNotFoundError):
        return f"{failure.filename} is not installed"
    stderr = failure.stderr.decode("utf-8", "replace") if isinstance(failure.stderr, bytes) \
        else failure.stderr or ""
    words, cmd = [], list(failure.cmd)
    while cmd:
        word = cmd.pop(0)
        if word == "-c":  # QUIET's config pairs say nothing about what failed
            cmd = cmd[1:]
        else:
            words.append(word)
    return f"{' '.join(words[:3])} failed ({stderr.strip()})"


def main():
    args = sys.argv[1:]
    push = "--push" in args
    args = [a for a in args if a != "--push"]
    if len(args) != 1 or args[0].startswith("-"):
        sys.exit(__doc__.split("\n\n")[1])
    root = os.path.abspath(args[0])
    if not os.path.isdir(root):
        sys.exit(without_userinfo(f"move-to-sourcehut: {root} is not a folder"))
    try:
        with open(REFERENCES) as f:
            address = sourcehut_address(f.read())
    except OSError:
        address = None
    if address is None:
        sys.exit(without_userinfo(
            f"move-to-sourcehut: no SourceHut address under a SourceHut heading in {REFERENCES}"))
    changed, waiting, skipped = 0, 0, 0
    for name in sorted(os.listdir(root)):
        project = os.path.join(root, name)
        if not os.path.isdir(project) or name.startswith("."):
            continue
        try:
            lines = move_project(project, push, address)
        except Skip as why:
            reason = str(why)
        except (subprocess.CalledProcessError, FileNotFoundError) as failure:
            reason = failure_reason(failure)
        else:
            changed += any(line != WAITING for line in lines)
            waiting += WAITING in lines
            for line in lines:
                print(without_userinfo(f"{name}: {line}"))
            continue
        skipped += 1
        print(without_userinfo(f"{name}: skipped, {reason}"))
    waits = f", {waiting} project(s) wait for --push" if waiting else ""
    if changed:
        print(f"move-to-sourcehut: changed {changed} project(s){waits}, skipped {skipped}")
    elif waiting:
        print(f"move-to-sourcehut: nothing changed{waits}, skipped {skipped}")
    else:
        print(f"move-to-sourcehut: nothing to do, skipped {skipped}")


if __name__ == "__main__":
    main()
