#!/usr/bin/env python3
"""Tests for scripts/export-public.py, the export into the public repo (shyrosa#94).

Most tests drive the command from outside, as test_chats_travel.py's prior art does:
a scratch private repo and a scratch public checkout in a temporary folder, then a
read of what the run left behind. Two tests read this repo itself: the strip over the
real rulebook, and the guard over the real skills.

No string in this file is a private term. The guard tests read their terms from
export/private-terms.txt at run time, so this file passes the guard when scripts/ is
exported. That list never ships, so in the public repo those tests skip, and so do
the rulebook tests, since the public rulebook arrives already stripped.
"""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SCRIPT = os.path.join(_HERE, "export-public.py")
_spec = importlib.util.spec_from_file_location("export_public", _SCRIPT)
ep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ep)

TERMS_FILE = os.path.join(_ROOT, "export", "private-terms.txt")
HAVE_TERMS = os.path.exists(TERMS_FILE)
NOREPLY = "omarzd <7592333+omarzd@users.noreply.github.com>"

ALLOWLIST = """\
# a comment
WORKFLOW-RULEBOOK.md
wire.sh
overlay/
!overlay/secret/LEDGER.md
export/public/README.md -> README.md
export/public/LICENSE -> LICENSE
"""

FILES = {
    "WORKFLOW-RULEBOOK.md": "# Rules\n\n- **A rule.** **(all)**, §7\n",
    "wire.sh": "#!/bin/sh\necho wired\n",
    "overlay/skill-a/SKILL.md": "skill a\n",
    "overlay/secret/LEDGER.md": "the ledger\n",
    "README.md": "the private README\n",
    "GRILL-QUEUE.md": "private queue\n",
    "export/public/README.md": "the public README\n",
    "export/public/LICENSE": "MIT License\n",
}


def real_terms_under(heading):
    """The terms in the real list's group under `# <heading>`."""
    terms, inside = [], False
    with open(TERMS_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                inside = line[1:].strip().lower() == heading.lower()
            elif line and inside:
                terms.append(line.removeprefix("word:").strip())
    return terms


def real_terms():
    """Every term in the real list, without its "word:" mark."""
    with open(TERMS_FILE) as f:
        return [line.strip().removeprefix("word:").strip() for line in f
                if line.strip() and not line.strip().startswith("#")]


def git(cwd, *args, env=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


def scratch_env(tmp, name, email):
    """An environment whose git config is a scratch one under `tmp`, as `name <email>`."""
    gitconfig = os.path.join(tmp, "gitconfig")
    with open(gitconfig, "w") as f:
        f.write(f"[user]\n\tname = {name}\n\temail = {email}\n"
                "[init]\n\tdefaultBranch = main\n")
    env = dict(os.environ, GIT_CONFIG_GLOBAL=gitconfig, GIT_CONFIG_NOSYSTEM="1")
    for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        env.pop(k, None)
    return env


def guard_hits(root, rels):
    """What the guard, with the real term list, finds in each of `rels` under `root`:
    in its path and in its text."""
    with open(TERMS_FILE) as f:
        terms = ep.load_terms(f.read())
    hits = []
    for rel in rels:
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            hits += ep.scan(rel, rel, terms) + ep.scan(rel, f.read(), terms)
    return hits


class Scratch(unittest.TestCase):
    """A private repo and a public checkout in one temporary folder."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = self._tmp.name
        # Someone else's identity, so the test proves the export ignores it.
        self.env = scratch_env(tmp, "Not The Manager", "wrong@example.com")

        self.priv = os.path.join(tmp, "private")
        self.pub = os.path.join(tmp, "public")
        self.bare = os.path.join(tmp, "public.git")
        for d in (self.priv, self.pub):
            os.makedirs(d)
            git(d, "init", "-q", env=self.env)
        git(tmp, "init", "-q", "--bare", self.bare, env=self.env)

        files = dict(FILES)
        files["export/allowlist.txt"] = ALLOWLIST
        files["export/private-terms.txt"] = "# a stand-in, since the real list never ships\nno-file-holds-this\n"
        if HAVE_TERMS:
            with open(TERMS_FILE) as f:
                files["export/private-terms.txt"] = f.read()
        self.write(self.priv, files)
        os.chmod(os.path.join(self.priv, "wire.sh"), 0o755)
        self.commit_private("start")

        # The public repo as #92 left it: a README and a LICENSE, pushed.
        self.write(self.pub, {"README.md": "the public README\n", "LICENSE": "MIT License\n"})
        git(self.pub, "add", "-A", env=self.env)
        git(self.pub, "commit", "-qm", "README and LICENSE", env=self.env)
        git(self.pub, "remote", "add", "origin", self.bare, env=self.env)
        git(self.pub, "push", "-q", "origin", "main", env=self.env)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, root, files):
        for rel, text in files.items():
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)

    def commit_private(self, msg):
        git(self.priv, "add", "-A", env=self.env)
        git(self.priv, "commit", "-qm", msg, env=self.env)
        return git(self.priv, "rev-parse", "HEAD", env=self.env)

    def export(self):
        return subprocess.run([sys.executable, _SCRIPT, "--from", self.priv, self.pub],
                              capture_output=True, text=True, env=self.env)

    def public_files(self):
        return set(git(self.pub, "ls-files", env=self.env).splitlines())

    def read_pub(self, rel):
        with open(os.path.join(self.pub, rel)) as f:
            return f.read()

    def git_dir(self):
        """{path: bytes} for every file in the public checkout's .git but its index, which
        a status refresh may rewrite."""
        root = os.path.join(self.pub, ".git")
        snap = {}
        for folder, _, names in os.walk(root):
            for name in names:
                path = os.path.join(folder, name)
                rel = os.path.relpath(path, root)
                if rel != "index":
                    with open(path, "rb") as f:
                        snap[rel] = f.read()
        return snap

    def export_in_process(self, fake):
        """Run the export in this process, with `fake(real_git, cwd, *args, **kw)` standing in
        for every git call; returns what it exited with."""
        real_git = ep.git
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(ep, "git", side_effect=lambda *a, **kw: fake(real_git, *a, **kw)), \
                mock.patch("sys.stdout"):
            with self.assertRaises(SystemExit) as raised:
                ep.main(["--from", self.priv, self.pub])
        return str(raised.exception.code)

    def assert_clean_and_unchanged(self):
        self.assertEqual(self.public_files(), {"README.md", "LICENSE"})
        self.assertEqual(git(self.pub, "status", "--porcelain", "--untracked-files=all", env=self.env), "")
        self.assertEqual(git(self.pub, "rev-list", "--count", "HEAD", env=self.env), "1")

    def assert_untouched(self, run, *said):
        """The run refused, said each of `said`, and left the public checkout as #92 did."""
        self.assertNotEqual(run.returncode, 0, run.stdout)
        for words in said:
            self.assertIn(words, run.stderr)
        self.assertEqual(self.public_files(), {"README.md", "LICENSE"})
        self.assertEqual(git(self.pub, "status", "--porcelain", "--untracked-files=all", env=self.env), "")
        self.assertEqual(git(self.pub, "rev-list", "--count", "HEAD", env=self.env), "1")


class ExportsTheAllowlist(Scratch):
    def test_public_holds_exactly_the_allowlisted_paths(self):
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.public_files(), {
            "WORKFLOW-RULEBOOK.md", "wire.sh", "overlay/skill-a/SKILL.md", "README.md", "LICENSE"})
        self.assertEqual(self.read_pub("README.md"), "the public README\n")
        self.assertTrue(os.access(os.path.join(self.pub, "wire.sh"), os.X_OK))

    def test_a_path_dropped_from_the_allowlist_is_removed(self):
        self.export()
        self.write(self.priv, {"export/allowlist.txt": ALLOWLIST.replace("wire.sh\n", "")})
        self.commit_private("drop wire.sh")
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("wire.sh", self.public_files())
        self.assertFalse(os.path.exists(os.path.join(self.pub, "wire.sh")))

    def test_files_come_from_head_not_the_working_tree(self):
        self.write(self.priv, {"overlay/skill-a/SKILL.md": "uncommitted edit\n",
                               "overlay/skill-b/SKILL.md": "untracked\n"})
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.read_pub("overlay/skill-a/SKILL.md"), "skill a\n")
        self.assertNotIn("overlay/skill-b/SKILL.md", self.public_files())

    def test_the_rulebook_leaves_without_its_citations(self):
        self.export()
        self.assertEqual(self.read_pub("WORKFLOW-RULEBOOK.md"), "# Rules\n\n- **A rule.** **(all)**\n")


class OneCommit(Scratch):
    def test_one_commit_named_by_the_private_hash_as_the_noreply_identity(self):
        before = git(self.pub, "rev-parse", "HEAD", env=self.env)
        head = git(self.priv, "rev-parse", "HEAD", env=self.env)
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(git(self.pub, "rev-list", "--count", f"{before}..HEAD", env=self.env), "1")
        self.assertEqual(git(self.pub, "log", "-1", "--format=%B", env=self.env), head)
        who = git(self.pub, "log", "-1", "--format=%an <%ae>|%cn <%ce>", env=self.env)
        self.assertEqual(who, f"{NOREPLY}|{NOREPLY}")
        self.assertEqual(git(self.pub, "status", "--porcelain", env=self.env), "")

    def test_it_never_pushes(self):
        pushed = git(self.bare, "rev-parse", "main", env=self.env)
        self.export()
        self.assertEqual(git(self.bare, "rev-parse", "main", env=self.env), pushed)

    def test_nothing_changed_makes_no_commit(self):
        self.export()
        before = git(self.pub, "rev-parse", "HEAD", env=self.env)
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(git(self.pub, "rev-parse", "HEAD", env=self.env), before)

    def test_two_sources_for_one_public_name_are_refused(self):
        self.write(self.priv, {"export/allowlist.txt": ALLOWLIST + "overlay/skill-a/SKILL.md -> wire.sh\n"})
        self.commit_private("clash")
        run = self.export()
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("wire.sh", run.stderr)
        self.assertEqual(self.public_files(), {"README.md", "LICENSE"})

    def test_a_listed_file_can_be_excluded(self):
        self.write(self.priv, {"export/allowlist.txt": ALLOWLIST + "!wire.sh\n"})
        self.commit_private("exclude wire.sh")
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("wire.sh", self.public_files())

    def test_a_listed_path_head_lacks_is_refused(self):
        self.write(self.priv, {"export/allowlist.txt": ALLOWLIST + "no-such-file.md\n"})
        self.commit_private("list a missing file")
        run = self.export()
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("no-such-file.md", run.stderr)

    def test_a_dirty_public_checkout_is_refused(self):
        self.write(self.pub, {"stray.txt": "x\n"})
        run = self.export()
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(self.public_files(), {"README.md", "LICENSE"})


class Hooks(Scratch):
    """A commit hook must not get text into the public commit message."""

    def hook(self, folder, name):
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        with open(path, "w") as f:
            f.write('#!/bin/sh\necho "added by a hook" >> "$1"\n')
        os.chmod(path, 0o755)

    def assert_bare_hash(self):
        head = git(self.priv, "rev-parse", "HEAD", env=self.env)
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(git(self.pub, "log", "-1", "--format=%B", env=self.env), head)

    def test_the_public_checkouts_own_hooks_add_nothing(self):
        hooks = os.path.join(self.pub, ".git", "hooks")
        self.hook(hooks, "prepare-commit-msg")
        self.hook(hooks, "commit-msg")
        self.assert_bare_hash()

    def test_a_machine_wide_hooks_path_adds_nothing(self):
        hooks = os.path.join(self._tmp.name, "global-hooks")
        self.hook(hooks, "prepare-commit-msg")
        self.hook(hooks, "commit-msg")
        with open(self.env["GIT_CONFIG_GLOBAL"], "a") as f:
            f.write(f"[core]\n\thooksPath = {hooks}\n")
        self.assert_bare_hash()


class Allowlist(Scratch):
    def allow(self, extra):
        self.write(self.priv, {"export/allowlist.txt": ALLOWLIST + extra})
        self.commit_private("allowlist: " + extra.strip())

    def test_a_folder_exclude_drops_everything_under_it(self):
        self.allow("!overlay/\n")
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse(any(p.startswith("overlay/") for p in self.public_files()))

    def test_an_exclude_that_matches_nothing_stops_the_run(self):
        self.allow("!overlay/no-such-skill/\n")
        self.assert_untouched(self.export(), "!overlay/no-such-skill/")

    def test_a_rename_cannot_leave_the_public_checkout(self):
        for dest in ("../escape.md", "docs/../../escape.md", "/tmp/escape.md", ".git/hooks/post-commit"):
            with self.subTest(dest=dest):
                self.write(self.priv, {"export/allowlist.txt": ALLOWLIST + f"GRILL-QUEUE.md -> {dest}\n"})
                self.commit_private("escape " + dest)
                before = self.git_dir()
                self.assert_untouched(self.export(), "outside the public checkout", dest)
                self.assertEqual(self.git_dir(), before)
                self.assertFalse(os.path.exists(os.path.join(self._tmp.name, "escape.md")))

    def test_a_non_ascii_name_is_exported(self):
        self.write(self.priv, {"overlay/café/SKILL.md": "café\n"})
        self.commit_private("non-ascii")
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.read_pub("overlay/café/SKILL.md"), "café\n")
        self.assertEqual(git(self.pub, "status", "--porcelain", env=self.env), "")


class Refusals(Scratch):
    def test_the_private_repo_itself_is_refused(self):
        run = subprocess.run([sys.executable, _SCRIPT, "--from", self.priv, self.priv],
                             capture_output=True, text=True, env=self.env)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("shares history", run.stderr)

    def test_a_checkout_sharing_a_commit_with_the_private_repo_is_refused(self):
        clone = os.path.join(self._tmp.name, "clone")
        git(self._tmp.name, "clone", "-q", self.priv, clone, env=self.env)
        before = git(clone, "rev-parse", "HEAD", env=self.env)
        run = subprocess.run([sys.executable, _SCRIPT, "--from", self.priv, clone],
                             capture_output=True, text=True, env=self.env)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("shares history", run.stderr)
        self.assertEqual(git(clone, "rev-parse", "HEAD", env=self.env), before)

    def test_an_empty_term_list_is_refused(self):
        self.write(self.priv, {"export/private-terms.txt": "# only a comment\n\n"})
        self.commit_private("empty terms")
        self.assert_untouched(self.export(), "term list")

    def test_a_gitlink_is_refused(self):
        sha = git(self.priv, "rev-parse", "HEAD", env=self.env)
        git(self.priv, "update-index", "--add", "--cacheinfo", f"160000,{sha},overlay/sub", env=self.env)
        git(self.priv, "commit", "-qm", "gitlink", env=self.env)
        self.assert_untouched(self.export(), "overlay/sub")

    def test_a_symlink_is_refused(self):
        os.symlink("SKILL.md", os.path.join(self.priv, "overlay/skill-a/link.md"))
        self.commit_private("symlink")
        self.assert_untouched(self.export(), "overlay/skill-a/link.md")

    def test_a_file_that_is_not_utf8_is_refused(self):
        with open(os.path.join(self.priv, "overlay/skill-a/data.bin"), "wb") as f:
            f.write(b"ok\n\xff\xfe\n")
        self.commit_private("not utf-8")
        self.assert_untouched(self.export(), "overlay/skill-a/data.bin")


class StagedAsScanned(Scratch):
    """What gets committed is exactly what the guard read."""

    def global_config(self, text):
        with open(self.env["GIT_CONFIG_GLOBAL"], "a") as f:
            f.write(text)

    def leak_filter(self):
        self.global_config('[filter "leak"]\n\tclean = sed s/skill/LEAK/\n')

    def test_a_stray_file_hidden_from_status_is_refused(self):
        self.global_config("[status]\n\tshowUntrackedFiles = no\n")
        self.write(self.pub, {"stray.txt": "never scanned\n"})
        run = self.export()
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("uncommitted changes", run.stderr)
        self.assertEqual(self.public_files(), {"README.md", "LICENSE"})
        self.assertEqual(git(self.pub, "rev-list", "--count", "HEAD", env=self.env), "1")

    def test_a_machine_wide_clean_filter_changes_nothing(self):
        self.leak_filter()
        attributes = os.path.join(self._tmp.name, "attributes")
        with open(attributes, "w") as f:
            f.write("* filter=leak\n")
        self.global_config(f"[core]\n\tattributesFile = {attributes}\n")
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(git(self.pub, "show", "HEAD:overlay/skill-a/SKILL.md", env=self.env), "skill a")

    def test_a_blob_unlike_the_scanned_bytes_is_refused_and_taken_back(self):
        self.leak_filter()
        with open(os.path.join(self.pub, ".git", "info", "attributes"), "w") as f:
            f.write("* filter=leak\n")
        self.assert_untouched(self.export(), "overlay/skill-a/SKILL.md")


class TakenBack(Scratch):
    """A check or step that fails after the run began writing puts the checkout back."""

    def test_a_message_other_than_the_hash_is_taken_back(self):
        def lying(real, cwd, *args, **kw):
            return "not the hash\n" if args[:2] == ("log", "-1") else real(cwd, *args, **kw)

        self.assertIn("not the bare hash", self.export_in_process(lying))
        self.assert_clean_and_unchanged()

    def test_a_staged_path_never_scanned_is_refused(self):
        # The status check is blinded, so the stray file reaches git add.
        self.write(self.pub, {"stray.txt": "never scanned\n"})
        seen = []

        def blind_first_status(real, cwd, *args, **kw):
            if "status" in args and not seen:
                seen.append(args)
                return ""
            return real(cwd, *args, **kw)

        said = self.export_in_process(blind_first_status)
        self.assertIn("what git staged is not what the guard scanned", said)
        self.assertIn("stray.txt", said)
        self.assertNotIn("stray.txt", self.public_files())
        self.assertEqual(git(self.pub, "rev-list", "--count", "HEAD", env=self.env), "1")

    def test_a_git_step_that_fails_after_writing_is_taken_back(self):
        def failing_add(real, cwd, *args, **kw):
            if "add" in args:
                raise subprocess.CalledProcessError(128, ["git", "add"], stderr=b"fatal: disk full")
            return real(cwd, *args, **kw)

        said = self.export_in_process(failing_add)
        self.assertIn("refused", said)
        self.assertIn("back as it was", said)
        self.assert_clean_and_unchanged()

    def test_a_public_name_that_is_also_a_folder_is_refused(self):
        self.write(self.priv, {"export/allowlist.txt": ALLOWLIST + "GRILL-QUEUE.md -> overlay/skill-a\n"})
        self.commit_private("a file over a folder")
        run = self.export()
        self.assertNotIn("Traceback", run.stderr)
        self.assert_untouched(run, "overlay/skill-a", "folder")


class Renames(Scratch):
    def test_a_case_only_rename_exports(self):
        self.assertEqual(self.export().returncode, 0)
        git(self.priv, "mv", "overlay/skill-a/SKILL.md", "overlay/skill-a/skill.md", env=self.env)
        git(self.priv, "commit", "-qm", "case only", env=self.env)
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("overlay/skill-a/skill.md", self.public_files())
        self.assertNotIn("overlay/skill-a/SKILL.md", self.public_files())
        self.assertEqual(git(self.pub, "status", "--porcelain", "--untracked-files=all", env=self.env), "")
        # And the run after it is clean too.
        self.assertEqual(self.export().returncode, 0)

    def test_a_folder_left_empty_is_removed(self):
        self.write(self.priv, {"overlay/skill-b/deep/SKILL.md": "b\n"})
        self.commit_private("skill b")
        self.assertEqual(self.export().returncode, 0)
        os.remove(os.path.join(self.priv, "overlay/skill-b/deep/SKILL.md"))
        self.commit_private("drop skill b")
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.pub, "overlay/skill-b")))
        self.assertTrue(os.path.isdir(os.path.join(self.pub, "overlay/skill-a")))


class ClearRefusals(Scratch):
    def test_a_public_checkout_with_no_commit_is_refused(self):
        empty = os.path.join(self._tmp.name, "empty")
        os.makedirs(empty)
        git(empty, "init", "-q", env=self.env)
        run = subprocess.run([sys.executable, _SCRIPT, "--from", self.priv, empty],
                             capture_output=True, text=True, env=self.env)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("no commit", run.stderr)
        self.assertNotIn("Traceback", run.stderr)
        self.assertEqual(git(empty, "status", "--porcelain", "--untracked-files=all", env=self.env), "")

    def test_a_file_name_that_is_not_utf8_is_refused(self):
        oid = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.priv, input=b"x\n",
                             check=True, capture_output=True, env=self.env).stdout.decode().strip()
        subprocess.run(["git", "update-index", "--add", "--cacheinfo",
                        b"100644," + oid.encode() + b",overlay/bad\xff.md"],
                       cwd=self.priv, check=True, capture_output=True, env=self.env)
        git(self.priv, "commit", "-qm", "a name that is not utf-8", env=self.env)
        run = self.export()
        self.assertNotIn("Traceback", run.stderr)
        self.assert_untouched(run, "overlay/bad")

    def test_a_rename_into_git_in_any_case_is_refused(self):
        for dest in (".GIT/description", ".Git/hooks/post-commit", "docs/.git/x", "docs/.gIt/x"):
            with self.subTest(dest=dest):
                self.write(self.priv, {"export/allowlist.txt": ALLOWLIST + f"GRILL-QUEUE.md -> {dest}\n"})
                self.commit_private("into .git " + dest)
                before = self.git_dir()
                self.assert_untouched(self.export(), "outside the public checkout", dest)
                self.assertEqual(self.git_dir(), before)
                self.assertFalse(os.path.exists(os.path.join(self.pub, "docs")))


@unittest.skipUnless(HAVE_TERMS, "the term list stays in the private repo")
class Guard(Scratch):
    def assert_refused(self, run, path, line, term):
        self.assert_untouched(run, f"{path}:{line}", term)

    def test_a_term_in_a_folder_name_stops_the_run(self):
        term = real_terms_under("Project names")[0]
        self.write(self.priv, {f"overlay/{term}-notes/SKILL.md": "clean\n"})
        self.commit_private("plant in a path")
        self.assert_untouched(self.export(), f"overlay/{term}-notes/SKILL.md: private term '{term}' in the path")

    def test_a_term_in_a_renamed_public_name_stops_the_run(self):
        term = real_terms_under("Project names")[0]
        self.write(self.priv, {"export/allowlist.txt": ALLOWLIST + f"GRILL-QUEUE.md -> {term}.md\n"})
        self.commit_private("plant in a rename")
        self.assert_untouched(self.export(), f"{term}.md: private term '{term}' in the path")

    def test_a_two_word_term_split_by_whitespace_stops_the_run(self):
        term = next(t for t in real_terms() if " " in t)
        first, rest = term.split(" ", 1)
        for text, line in ((f"intro\nworks at {first}\n   {rest} now\n", 2),
                           (f"works at {first}    {rest}\n", 1),
                           (f"works at {first}\t{rest}\n", 1)):
            with self.subTest(text=text):
                self.write(self.priv, {"overlay/skill-a/SKILL.md": text})
                self.commit_private("plant split")
                self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", line, term)

    def added_for_the_reviews_gaps(self):
        """The entries shyrosa#123 added, read from the list: the last two project names and
        the email's first half, which stands alone."""
        added = real_terms_under("Project names")[-2:] + [
            t for t in real_terms_under("Email addresses") if "@" not in t]
        self.assertEqual(len(added), 3)
        return added

    def fresh_public(self):
        """The public checkout as #92 left it, so one subtest's failure cannot reach the next."""
        git(self.pub, "reset", "-q", "--hard", "origin/main", env=self.env)
        git(self.pub, "clean", "-fdq", env=self.env)

    def test_the_entries_added_for_the_reviews_gaps_stop_the_run_bare(self):
        for term in self.added_for_the_reviews_gaps():
            with self.subTest(term=term):
                self.fresh_public()
                self.write(self.priv, {"overlay/skill-a/SKILL.md": f"intro\nsee {term} now\n"})
                self.commit_private("plant bare")
                self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 2, term)

    def test_a_many_part_term_matches_across_a_space_a_hyphen_an_underscore_or_nothing(self):
        parts_of = lambda t: re.split(r"[\s-]+", t)
        many = [t for t in real_terms() if len(parts_of(t)) > 1]
        self.assertTrue(many)
        for term in many:
            for gap in (" ", "-", "_", ""):
                with self.subTest(term=term, gap=gap):
                    self.fresh_public()
                    self.write(self.priv, {"overlay/skill-a/SKILL.md": f"intro\nsee {gap.join(parts_of(term))} now\n"})
                    self.commit_private("plant gap")
                    self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 2, term)

    def test_a_many_part_term_matches_across_each_unicode_dash(self):
        term = next(t for t in real_terms() if "-" in t)
        first, rest = term.split("-", 1)
        for dash in ("‐", "‑", "‒", "–", "—", "―", "−"):
            with self.subTest(dash=hex(ord(dash))):
                self.fresh_public()
                self.write(self.priv, {"overlay/skill-a/SKILL.md": f"intro\nsee {first}{dash}{rest} now\n"})
                self.commit_private("plant dash")
                self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 2, term)

    def test_a_many_part_term_in_a_path_matches_across_a_space_a_hyphen_an_underscore_or_nothing(self):
        term = next(t for t in real_terms() if " " in t)
        for gap in ("-", "_", ""):
            with self.subTest(gap=gap):
                self.fresh_public()
                name = f"overlay/{gap.join(term.split())}/SKILL.md"
                self.write(self.priv, {name: "clean\n"})
                self.commit_private("plant in a path")
                self.assert_untouched(self.export(), f"{name}: private term '{term}' in the path")

    def test_a_hyphenated_term_wrapped_inside_a_comment_stops_the_run(self):
        term = next(t for t in real_terms() if "-" in t)
        first, rest = term.split("-", 1)
        for text in (f"# at {first}\n# {rest}\n", f"# at {first}-\n# {rest}\n"):
            with self.subTest(text=text):
                self.write(self.priv, {"overlay/skill-a/SKILL.md": text})
                self.commit_private("plant in a comment")
                self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 1, term)

    def test_a_letter_between_the_parts_of_a_term_passes(self):
        term = next(t for t in real_terms() if " " in t or "-" in t)
        first, rest = re.split(r"[\s-]+", term, maxsplit=1)
        self.write(self.priv, {"overlay/skill-a/SKILL.md": f"{first}x{rest}\n"})
        self.commit_private("not the term")
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_a_term_hidden_by_invisible_characters_stops_the_run(self):
        term = real_terms_under("Project names")[0]
        for mark in ("­", "​", "‌", "‍", "⁠", "﻿"):
            with self.subTest(mark=hex(ord(mark))):
                self.write(self.priv, {"overlay/skill-a/SKILL.md": f"see {term[:2]}{mark}{term[2:]}\n"})
                self.commit_private("plant hidden")
                self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 1, term)

    def test_every_invisible_character_is_dropped(self):
        term = real_terms_under("Project names")[0]
        for mark in ("‎", "⁦", "᠎", "\U000e0041", "͏", "ᅟ", "ᅠ",
                     "ㅤ", "︀", "️"):
            with self.subTest(mark=hex(ord(mark))):
                self.write(self.priv, {"overlay/skill-a/SKILL.md": f"see {term[:2]}{mark}{term[2:]}\n"})
                self.commit_private("plant hidden")
                self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 1, term)

    def test_fullwidth_letters_fold_to_the_term(self):
        term = real_terms_under("Project names")[0]
        wide = "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in term)
        self.write(self.priv, {"overlay/skill-a/SKILL.md": f"intro\nsee {wide}\n"})
        self.commit_private("plant fullwidth")
        self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 2, term)

    def test_a_two_word_term_wrapped_inside_a_comment_or_quote_stops_the_run(self):
        term = next(t for t in real_terms() if " " in t)
        first, rest = term.split(" ", 1)
        for text in (f"# at {first}\n# {rest}\n", f"// at {first}\n  // {rest}\n",
                     f" * at {first}\n * {rest}\n", f"> at {first}\n> {rest}\n",
                     f"#at {first}\n#{rest}\n", f"# at {first}\n#\n# {rest}\n",
                     f"> > at {first}\n> > {rest}\n", f"/// at {first}\n/// {rest}\n",
                     f"  # > at {first}\n  # > {rest}\n"):
            with self.subTest(text=text):
                self.write(self.priv, {"overlay/skill-a/SKILL.md": text})
                self.commit_private("plant in a comment")
                self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 1, term)

    def test_the_term_list_is_read_from_head(self):
        term = real_terms_under("Project names")[0]
        self.write(self.priv, {"overlay/skill-a/SKILL.md": f"{term}\n"})
        self.commit_private("plant")
        # An uncommitted, emptied term list must not let the committed term through.
        self.write(self.priv, {"export/private-terms.txt": "# emptied, not committed\nnothing-matches-this\n"})
        self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 1, term)

    def test_a_planted_term_stops_the_run_and_writes_nothing(self):
        term = real_terms_under("Project names")[0]
        self.write(self.priv, {"overlay/skill-a/SKILL.md": f"skill a\nsee the {term} board\n"})
        self.commit_private("plant")
        self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 2, term)

    def test_a_term_matches_whatever_its_case(self):
        term = real_terms_under("Employer")[0]
        self.write(self.priv, {"wire.sh": f"#!/bin/sh\n# {term.upper()}\n"})
        self.commit_private("plant")
        self.assert_refused(self.export(), "wire.sh", 2, term)

    def test_the_placeholder_home_paths_pass(self):
        self.write(self.priv, {"overlay/skill-a/SKILL.md": "a machine path (`/Users/...`, `/home/...`)\n"})
        self.commit_private("placeholder")
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_a_real_home_path_stops_the_run(self):
        for user in real_terms_under("Machine user names"):
            for text in (f"/Users/{user}/dev", f"/home/{user}/dev", f"-Users-{user}-dev-app"):
                with self.subTest(text=text):
                    self.write(self.priv, {"overlay/skill-a/SKILL.md": text + "\n"})
                    self.commit_private("plant " + text)
                    self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 1, user)

    def test_a_user_name_inside_a_longer_word_stops_the_run(self):
        user = real_terms_under("Machine user names")[0]
        self.write(self.priv, {"overlay/skill-a/SKILL.md": f"x{user}2\n"})
        self.commit_private("plant")
        self.assert_refused(self.export(), "overlay/skill-a/SKILL.md", 1, user)

    def test_a_whole_word_term_inside_a_longer_word_passes(self):
        name = real_terms_under("Names")[0]
        self.write(self.priv, {"overlay/skill-a/SKILL.md": f"{name}zd and 3{name}x\n"})
        self.commit_private("longer words")
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_the_renamed_file_is_named_by_its_public_path(self):
        term = real_terms_under("Project names")[0]
        self.write(self.priv, {"export/public/README.md": f"about {term}\n"})
        self.commit_private("plant")
        self.assert_refused(self.export(), "README.md", 1, term)


with open(os.path.join(_ROOT, "WORKFLOW-RULEBOOK.md")) as _f:
    CITED = "**Provenance lives in" in _f.read()


@unittest.skipUnless(CITED, "the public rulebook has already left without its citations")
class RealRulebook(unittest.TestCase):
    """The strip over this repo's own rulebook."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(_ROOT, "WORKFLOW-RULEBOOK.md")) as f:
            cls.before = f.read()
        cls.after = ep.strip_citations(cls.before)

    def test_no_ledger_section_is_left(self):
        rest = self.after.replace("GRILL-QUEUE.md §8", "")
        self.assertNotIn("§", rest)
        self.assertNotIn("LEDGER", self.after)
        self.assertNotIn("(ledger", self.after)
        self.assertNotIn("Superseded", self.after)

    def test_the_grill_me_example_keeps_its_section(self):
        self.assertIn("`/grill-me GRILL-QUEUE.md §8 the scribe rule`", self.after)

    def test_the_audience_tags_stay(self):
        tag = re.compile(r"\*\*\((?:D|W|F|M|all)\)\*\*")
        self.assertEqual(len(tag.findall(self.after)), len(tag.findall(self.before)))

    def test_no_tag_keeps_a_trailing_comma_or_a_stray_line(self):
        self.assertNotRegex(self.after, r"\)\*\*,")
        self.assertNotRegex(self.after, r"(?m)^\s*\.")

    def test_the_rule_text_stays(self):
        # The strip removes only citations, so every word left of them survives.
        cut = re.compile(r"§\d+|Superseded|\(ledger[^)]*\)|LEDGER\.md")
        lost = set(re.findall(r"[A-Za-z]{4,}", self.before)) - set(re.findall(r"[A-Za-z]{4,}", self.after))
        lost -= set(re.findall(r"[A-Za-z]{4,}", " ".join(cut.findall(self.before))))
        opening = self.before.split("**Provenance lives in", 1)[1].split("\n\n", 1)[0]
        opening = "Provenance " + opening
        lost -= set(re.findall(r"[A-Za-z]{4,}", opening))
        self.assertEqual(lost, set())

    def test_an_inline_citation_of_several_sections_goes_whole(self):
        self.assertEqual(ep.strip_citations("(a director, §7, §8) runs"), "(a director) runs")

    def test_the_opening_ledger_paragraph_is_gone(self):
        self.assertNotIn("Provenance lives in", self.after)
        self.assertIn("**Audience tags** say who a rule binds", self.after)


# Spelled in two halves, so the export does not strip these samples from this file.
L, U = "ledg" "er", "LEDG" "ER"


class OtherFilesLoseTheirCitations(Scratch):
    """Shyrosa#98: a ledger citation goes from every exported file, not only the rulebook."""

    def test_a_file_outside_the_rulebook_leaves_without_its_ledger_citation(self):
        self.write(self.priv, {
            "overlay/skill-a/SKILL.md": f"bind (measured both, g25 round 2, {U} §2). Next.\n",
            "wire.sh": f"#!/bin/sh\n# rulings only ({L} §6)\necho wired\n",
        })
        self.commit_private("cite the ledger")
        run = self.export()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.read_pub("overlay/skill-a/SKILL.md"), "bind (measured both, g25 round 2). Next.\n")
        self.assertEqual(self.read_pub("wire.sh"), "#!/bin/sh\n# rulings only\necho wired\n")


class StripLedgerMentions(unittest.TestCase):
    def strip(self, text):
        return ep.strip_ledger_mentions(text)

    def test_a_trailing_section_in_a_parenthesis(self):
        self.assertEqual(self.strip(f"a (measured, g25, {U} §2) b"), "a (measured, g25) b")

    def test_a_parenthesis_that_is_only_a_citation_goes_whole(self):
        self.assertEqual(self.strip(f"never drift apart ({L} §7, sitting g27)."), "never drift apart.")

    def test_a_dated_ruling_keeps_its_date(self):
        self.assertEqual(self.strip(f"# g28 (rulings {L} §7, 2026-09-01): the disk"),
                         "# g28 (2026-09-01): the disk")

    def test_and_ledger_section(self):
        self.assertEqual(self.strip(f"Procedure: `x` and {L} §9.\n"), "Procedure: `x`.\n")

    def test_the_provenance_clause(self):
        self.assertEqual(self.strip(f"Ruled in g04, GRILL-QUEUE §2; provenance in the {L}, §8.\n"),
                         "Ruled in g04, GRILL-QUEUE §2.\n")

    def test_the_ledger_link_clause(self):
        self.assertEqual(self.strip("binds you is [`WORKFLOW-RULEBOOK.md`](WORKFLOW-RULEBOOK.md); why it binds you is\n"
                                    f"[`{U}.md`]({U}.md).\n"),
                         "binds you is [`WORKFLOW-RULEBOOK.md`](WORKFLOW-RULEBOOK.md).\n")

    def test_a_section_sign_that_cites_something_else_stays(self):
        text = "`/grill-me GRILL-QUEUE.md §8 the rule`"
        self.assertEqual(self.strip(text), text)


class RealExportedFiles(unittest.TestCase):
    """Every file the real allowlist takes in, as the export would write it."""

    def test_none_keeps_a_ledger_citation(self):
        tracked = subprocess.run(["git", "ls-files"], cwd=_ROOT, check=True,
                                 capture_output=True, text=True).stdout.splitlines()
        with open(os.path.join(_ROOT, "export", "allowlist.txt")) as f:
            includes, excludes, renames = ep.parse_allowlist(f.read())
        cited = re.compile(r"(?i)\bledger\b.{0,3}§\s*\d|\[`LEDGER\.md`\]")
        left = []
        for rel in tracked:
            if any(ep.covers(x, rel) for x in excludes):
                continue
            if rel not in renames and not any(ep.covers(i, rel) for i in includes):
                continue
            try:
                with open(os.path.join(_ROOT, rel), encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            if rel == ep.RULEBOOK:
                text = ep.strip_citations(text)
            left += [f"{rel}: {m.group(0)}" for m in cited.finditer(ep.strip_ledger_mentions(text))]
        self.assertEqual(left, [])


@unittest.skipUnless(HAVE_TERMS, "the term list stays in the private repo")
class RealSkills(unittest.TestCase):
    def test_the_guard_finds_nothing_in_the_skills(self):
        with open(os.path.join(_ROOT, "export", "allowlist.txt")) as f:
            _, excludes, _ = ep.parse_allowlist(f.read())
        self.assertIn("overlay/log-ruling/LEDGER.md", excludes)
        tracked = subprocess.run(["git", "ls-files", "overlay"], cwd=_ROOT, check=True,
                                 capture_output=True, text=True).stdout.split()
        self.assertEqual(guard_hits(_ROOT, [rel for rel in tracked if rel not in excludes]), [])


SETUP_SKILL = os.path.join(_ROOT, "overlay", "setup-matt-pocock-skills", "SKILL.md")
PUBLIC_README = os.path.join(_ROOT, "export", "public", "README.md")


@unittest.skipUnless(os.path.exists(PUBLIC_README), "the public repo ships this file as README.md")
class PublicReadmeInstall(unittest.TestCase):
    """The install section names what the setup skill needs before it can run (shyrosa#124)."""

    @classmethod
    def setUpClass(cls):
        with open(PUBLIC_README) as f:
            readme = f.read()
        cls.install = readme.split("## Install", 1)[1].split("\n## ", 1)[0]
        with open(SETUP_SKILL) as f:
            cls.clis = re.findall(r"uses the \[?`([\w-]+)`", f.read())

    def test_the_setup_skill_still_names_its_tracker_clis(self):
        self.assertIn("gh", self.clis)

    def test_each_tracker_cli_is_named_with_its_login(self):
        for cli in self.clis:
            with self.subTest(cli=cli):
                self.assertIn(f"`{cli} auth login`", self.install)

    def test_the_trackers_without_a_cli_are_named(self):
        self.assertIn("local markdown", self.install.lower())
        self.assertIn("Linear", self.install)


@unittest.skipUnless(HAVE_TERMS, "the term list stays in the private repo")
class RealExport(unittest.TestCase):
    """The real allowlist over this repo's HEAD, into a scratch public checkout that holds
    what the public repo holds before its first export: the README and the LICENSE.
    It reads HEAD, as the export does, so an uncommitted edit is not tested (shyrosa#124)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = cls._tmp.name
        cls.env = scratch_env(tmp, "Scratch", "scratch@example.com")
        cls.pub = os.path.join(tmp, "public")
        os.makedirs(cls.pub)
        git(cls.pub, "init", "-q", env=cls.env)
        for name in ("README.md", "LICENSE"):
            with open(os.path.join(cls.pub, name), "w") as f:
                f.write(git(_ROOT, "show", f"HEAD:export/public/{name}") + "\n")
        git(cls.pub, "add", "-A", env=cls.env)
        git(cls.pub, "commit", "-qm", "README and LICENSE", env=cls.env)
        cls.exported = subprocess.run([sys.executable, _SCRIPT, "--from", _ROOT, cls.pub],
                                      capture_output=True, text=True, env=cls.env)
        cls.files = set(git(cls.pub, "ls-files", env=cls.env).splitlines())

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_export_refuses_nothing(self):
        self.assertEqual(self.exported.returncode, 0, self.exported.stderr)
        self.assertEqual(self.exported.stderr, "")

    def test_what_landed_holds_no_private_word(self):
        self.assertEqual(guard_hits(self.pub, sorted(self.files)), [])

    def test_matts_vendored_skills_ship_whole(self):
        vendored = set(git(_ROOT, "ls-tree", "-r", "--name-only", "HEAD", "upstream/").splitlines())
        self.assertIn("upstream/grill-with-docs/SKILL.md", vendored)
        self.assertLessEqual(vendored, self.files)

    def test_the_chats_script_and_its_test_stay_private(self):
        self.assertNotIn("scripts/chats-travel.py", self.files)
        self.assertNotIn("scripts/test_chats_travel.py", self.files)
        self.assertNotIn("scripts/chats.py", self.files)
        self.assertNotIn("scripts/test_chats.py", self.files)
        self.assertIn("scripts/export-public.py", self.files)


if __name__ == "__main__":
    unittest.main()
