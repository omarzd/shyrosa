#!/usr/bin/env python3
"""Tests for scripts/rename-glossary.py, the CONTEXT.md to GLOSSARY.md rename (shyrosa#105).

Each test drives the command from outside, as test_chats_travel.py and
test_export_public.py do: a scratch dev root of scratch git repos in a temporary
folder, then a read of what the run left on disk and in git.
"""
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "rename-glossary.py")
GLOBAL_IDENTITY = "Not The Manager <global@example.com>"
OLD_NAMES = ("CONTEXT.md", "CONTEXT-MAP.md", "CONTEXT-FORMAT.md")


def git(cwd, *args, env=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


class Scratch(unittest.TestCase):
    """A dev root in a temporary folder, with a git identity that is not the manager's."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = self._tmp.name
        # Isolate identity resolution from the machine running the tests.
        gitconfig = os.path.join(tmp, "gitconfig")
        with open(gitconfig, "w") as f:
            f.write("[user]\n\tname = Not The Manager\n\temail = global@example.com\n"
                    "[init]\n\tdefaultBranch = main\n")
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=gitconfig, GIT_CONFIG_NOSYSTEM="1")
        for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            self.env.pop(k, None)
        self.root = os.path.join(tmp, "dev")
        os.makedirs(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def repo(self, name, files, remote=None):
        """A project under the dev root holding `files`, committed once."""
        path = os.path.join(self.root, name)
        os.makedirs(path)
        git(path, "init", "-q", env=self.env)
        self.write(path, files)
        git(path, "add", "-A", env=self.env)
        git(path, "commit", "-qm", "start", env=self.env)
        if remote:
            git(path, "remote", "add", "origin", remote, env=self.env)
        return path

    def write(self, path, files):
        for rel, text in files.items():
            full = os.path.join(path, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb" if isinstance(text, bytes) else "w") as f:
                f.write(text)

    def read(self, path, rel):
        with open(os.path.join(path, rel)) as f:
            return f.read()

    def run_script(self):
        r = subprocess.run([sys.executable, _SCRIPT, self.root], capture_output=True,
                           text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def commits(self, path):
        return int(git(path, "rev-list", "--count", "HEAD", env=self.env))

    def snapshot(self, path):
        """Every file under `path`, .git included, as bytes: proof a run left it alone."""
        seen = {}
        for folder, _, names in os.walk(path):
            for name in names:
                full = os.path.join(folder, name)
                with open(full, "rb") as f:
                    seen[os.path.relpath(full, path)] = f.read()
        return seen

    def old_name_mentions(self, path):
        """Tracked files whose text still holds one of the three old names."""
        hits = []
        for rel in git(path, "ls-files", env=self.env).splitlines():
            if any(old in self.read(path, rel) for old in OLD_NAMES):
                hits.append(rel)
        return hits


class PlainRename(Scratch):

    def setUp(self):
        super().setUp()
        self.app = self.repo("app", {
            "CONTEXT.md": "# Glossary\n\nAn **order** is what a customer places.\n",
            "README.md": "Read CONTEXT.md first.\n",
            "docs/adr/0001-orders.md": "The term is in `CONTEXT.md`.\n",
            "docs/handoffs/old.md": "I updated CONTEXT.md and ./CONTEXT.md again.\n",
            "src/main.py": "print('no mention here')\n",
        })
        self.out = self.run_script()

    def test_the_glossary_has_its_new_name(self):
        self.assertFalse(os.path.exists(os.path.join(self.app, "CONTEXT.md")))
        self.assertEqual(self.read(self.app, "GLOSSARY.md"),
                         "# Glossary\n\nAn **order** is what a customer places.\n")

    def test_no_old_name_survives_in_tracked_text_records_included(self):
        self.assertEqual(self.old_name_mentions(self.app), [])
        self.assertEqual(self.read(self.app, "docs/handoffs/old.md"),
                         "I updated GLOSSARY.md and ./GLOSSARY.md again.\n")
        self.assertEqual(self.read(self.app, "README.md"), "Read GLOSSARY.md first.\n")

    def test_one_commit_as_the_global_identity_and_a_clean_tree(self):
        self.assertEqual(self.commits(self.app), 2)
        self.assertEqual(git(self.app, "log", "-1", "--format=%an <%ae>", env=self.env), GLOBAL_IDENTITY)
        self.assertEqual(git(self.app, "log", "-1", "--format=%cn <%ce>", env=self.env), GLOBAL_IDENTITY)
        self.assertEqual(git(self.app, "status", "--porcelain", env=self.env), "")

    def test_git_sees_a_rename_not_a_delete_and_add(self):
        status = git(self.app, "show", "-M", "--name-status", "--format=", "HEAD", env=self.env)
        self.assertIn("R100\tCONTEXT.md\tGLOSSARY.md", status)

    def test_it_prints_what_it_renamed_and_rewrote(self):
        self.assertIn("app", self.out)
        self.assertIn("CONTEXT.md -> GLOSSARY.md", self.out)
        for rel in ("README.md", "docs/adr/0001-orders.md", "docs/handoffs/old.md"):
            self.assertIn(rel, self.out)
        self.assertNotIn("src/main.py", self.out)

    def test_a_second_run_finds_nothing_to_do(self):
        out = self.run_script()
        self.assertEqual(self.commits(self.app), 2)
        self.assertIn("nothing to do", out)


class CommitIdentity(Scratch):

    def test_repo_identity_overrides_global_identity_for_author_and_committer(self):
        app = self.repo("sourcehut", {"CONTEXT.md": "glossary\n"})
        git(app, "config", "user.name", "SourceHut User", env=self.env)
        git(app, "config", "user.email", "sourcehut@example.com", env=self.env)
        self.run_script()
        self.assertEqual(self.commits(app), 2)
        for fmt in ("%an <%ae>", "%cn <%ce>"):
            self.assertEqual(git(app, "log", "-1", "--format=" + fmt, env=self.env),
                             "SourceHut User <sourcehut@example.com>")


    def test_missing_identity_is_refused_without_changes_and_next_repo_runs(self):
        missing = self.repo("a-missing", {"CONTEXT.md": "glossary\n"})
        ready = self.repo("b-ready", {"CONTEXT.md": "glossary\n"})
        git(ready, "config", "user.name", "Ready User", env=self.env)
        git(ready, "config", "user.email", "ready@example.com", env=self.env)
        # Prevent Git's OS-derived fallback as well as global/system config.
        with open(self.env["GIT_CONFIG_GLOBAL"], "w") as f:
            f.write("[user]\n\tuseConfigOnly = true\n")
        self.env.pop("EMAIL", None)
        before = git(missing, "rev-parse", "HEAD", env=self.env)
        out = self.run_script()
        self.assertIn("a-missing: skipped, no resolvable git identity", out)
        self.assertEqual(git(missing, "rev-parse", "HEAD", env=self.env), before)
        self.assertEqual(git(missing, "status", "--porcelain", env=self.env), "")
        self.assertEqual(self.read(missing, "CONTEXT.md"), "glossary\n")
        self.assertFalse(os.path.exists(os.path.join(missing, "GLOSSARY.md")))
        self.assertEqual(self.commits(ready), 2)
        self.assertIn("b-ready: committed", out)


class MapAndFormat(Scratch):

    def test_map_and_format_are_renamed_wherever_they_appear(self):
        app = self.repo("multi", {
            "CONTEXT.md": "root glossary\n",
            "CONTEXT-MAP.md": "See src/ordering/CONTEXT.md and src/billing/CONTEXT.md.\n",
            "src/ordering/CONTEXT.md": "ordering\n",
            "src/billing/CONTEXT.md": "billing\n",
            "docs/CONTEXT-FORMAT.md": "How CONTEXT-MAP.md and CONTEXT-FORMAT.md are laid out.\n",
        })
        self.run_script()
        files = set(git(app, "ls-files", env=self.env).splitlines())
        self.assertEqual(files, {"GLOSSARY.md", "GLOSSARY-MAP.md", "src/ordering/GLOSSARY.md",
                                 "src/billing/GLOSSARY.md", "docs/GLOSSARY-FORMAT.md"})
        self.assertEqual(self.read(app, "GLOSSARY-MAP.md"),
                         "See src/ordering/GLOSSARY.md and src/billing/GLOSSARY.md.\n")
        self.assertEqual(self.read(app, "docs/GLOSSARY-FORMAT.md"),
                         "How GLOSSARY-MAP.md and GLOSSARY-FORMAT.md are laid out.\n")
        self.assertEqual(self.commits(app), 2)

    def test_a_longer_name_that_ends_the_same_way_is_left(self):
        app = self.repo("near", {
            "CONTEXT.md": "glossary\n",
            "notes.md": "BOUNDED-CONTEXT.md, MYCONTEXT.md and CONTEXT.mdx stay; "
                        "CONTEXT.md goes, CONTEXT.md-based too.\n",
        })
        self.run_script()
        self.assertEqual(self.read(app, "notes.md"),
                         "BOUNDED-CONTEXT.md, MYCONTEXT.md and CONTEXT.mdx stay; "
                         "GLOSSARY.md goes, GLOSSARY.md-based too.\n")


class SectionPointers(Scratch):

    def test_context_section_becomes_glossary_section_and_bare_context_stays(self):
        app = self.repo("sections", {
            "CONTEXT.md": "glossary\n",
            "src/labels.test.ts": "// CONTEXT \u00a74 and CONTEXT \u00a7 12, see CONTEXT.md\n",
            "notes.md": "The CONTEXT of the order, CONTEXT, BOUNDED-CONTEXT \u00a71 and "
                        "CONTEXT 5 stay.\n",
        })
        self.run_script()
        self.assertEqual(self.read(app, "src/labels.test.ts"),
                         "// GLOSSARY \u00a74 and GLOSSARY \u00a7 12, see GLOSSARY.md\n")
        self.assertEqual(self.read(app, "notes.md"),
                         "The CONTEXT of the order, CONTEXT, BOUNDED-CONTEXT \u00a71 and "
                         "CONTEXT 5 stay.\n")
        self.assertEqual(self.commits(app), 2)

    def test_a_utf8_file_holding_a_nul_byte_is_rewritten(self):
        app = self.repo("nul", {
            "CONTEXT.md": "glossary\n",
            "src/fx.test.ts": b'// CONTEXT \xc2\xa73, see CONTEXT.md\nx.join("\0");\n',
        })
        self.run_script()
        with open(os.path.join(app, "src/fx.test.ts"), "rb") as f:
            self.assertEqual(f.read(),
                             b'// GLOSSARY \xc2\xa73, see GLOSSARY.md\nx.join("\0");\n')

    def test_the_commit_message_names_the_section_rewrite_too(self):
        app = self.repo("msg", {"CONTEXT.md": "glossary\n"})
        self.run_script()
        message = git(app, "log", "-1", "--format=%B", env=self.env)
        self.assertIn("CONTEXT §", message)
        self.assertIn("GLOSSARY §", message)


class LeftAlone(Scratch):

    def test_a_dirty_repo_is_skipped_and_listed_its_tree_unchanged(self):
        dirty = self.repo("dirty", {"CONTEXT.md": "glossary\n", "a.md": "see CONTEXT.md\n"})
        self.write(dirty, {"a.md": "see CONTEXT.md, work in progress\n"})
        untracked = self.repo("untracked", {"CONTEXT.md": "glossary\n"})
        self.write(untracked, {"new.md": "a draft\n"})
        before = {p: self.snapshot(p) for p in (dirty, untracked)}
        out = self.run_script()
        for p in (dirty, untracked):
            self.assertEqual(self.snapshot(p), before[p])
            self.assertEqual(self.commits(p), 1)
        self.assertIn("dirty: skipped, tree not clean", out)
        self.assertIn("untracked: skipped, tree not clean", out)

    def test_a_matt_clone_is_untouched(self):
        for name, remote in (("matt-https", "https://github.com/mattpocock/skills.git"),
                             ("matt-ssh", "git@github.com:mattpocock/skills.git")):
            clone = self.repo(name, {"CONTEXT.md": "his glossary\n", "README.md": "see CONTEXT.md\n"},
                              remote=remote)
            before = self.snapshot(clone)
            out = self.run_script()
            self.assertEqual(self.snapshot(clone), before)
            self.assertIn(f"{name}: skipped, a Matt clone", out)

    def test_a_lookalike_owner_is_not_a_matt_clone(self):
        app = self.repo("fork", {"CONTEXT.md": "glossary\n"},
                        remote="https://github.com/notmattpocock/skills.git")
        self.run_script()
        self.assertEqual(self.read(app, "GLOSSARY.md"), "glossary\n")

    def test_a_vendored_upstream_folder_is_untouched(self):
        app = self.repo("vendor", {
            "CONTEXT.md": "glossary\n",
            "upstream/grill-with-docs/SKILL.md": "Matt reads CONTEXT.md here.\n",
            "upstream/domain/CONTEXT-FORMAT.md": "his format\n",
            "overlay/x/SKILL.md": "ours reads CONTEXT.md\n",
        })
        self.run_script()
        self.assertEqual(self.read(app, "upstream/grill-with-docs/SKILL.md"),
                         "Matt reads CONTEXT.md here.\n")
        self.assertTrue(os.path.exists(os.path.join(app, "upstream/domain/CONTEXT-FORMAT.md")))
        self.assertEqual(self.read(app, "overlay/x/SKILL.md"), "ours reads GLOSSARY.md\n")
        self.assertEqual(self.read(app, "GLOSSARY.md"), "glossary\n")

    def test_a_project_without_a_root_glossary_is_not_handled(self):
        app = self.repo("plain", {"README.md": "mentions CONTEXT.md\n",
                                  "src/ordering/CONTEXT.md": "nested only\n"})
        before = self.snapshot(app)
        self.run_script()
        self.assertEqual(self.snapshot(app), before)

    def test_binary_files_are_left_and_symlinks_follow_the_rename(self):
        app = self.repo("bin", {"CONTEXT.md": "glossary\n",
                                "logo.png": b"\x89PNG\0CONTEXT.md\0"})
        os.symlink("CONTEXT.md", os.path.join(app, "link.md"))
        git(app, "add", "link.md", env=self.env)
        git(app, "commit", "-qm", "link", env=self.env)
        self.run_script()
        with open(os.path.join(app, "logo.png"), "rb") as f:
            self.assertEqual(f.read(), b"\x89PNG\0CONTEXT.md\0")
        self.assertEqual(os.readlink(os.path.join(app, "link.md")), "GLOSSARY.md")
        self.assertEqual(self.read(app, "link.md"), "glossary\n")
        self.assertEqual(git(app, "status", "--porcelain", env=self.env), "")

    def test_a_root_glossary_git_does_not_track_is_skipped_every_run(self):
        app = self.repo("ignored", {".gitignore": "CONTEXT.md\n", "a.md": "see CONTEXT.md\n"})
        self.write(app, {"CONTEXT.md": "local only\n"})
        before = self.snapshot(app)
        for _ in range(2):
            out = self.run_script()
            self.assertIn("ignored: skipped, its root CONTEXT.md is not a file git tracks", out)
        self.assertEqual(self.snapshot(app), before)

    def test_a_failed_step_puts_the_project_back(self):
        app = self.repo("locked", {"CONTEXT.md": "glossary\n", "a.md": "see CONTEXT.md\n",
                                   "b.md": "see CONTEXT.md\n"})
        # Read-only: git still sees a clean tree, but the rewrite cannot write b.md.
        os.chmod(os.path.join(app, "b.md"), 0o444)
        out = self.run_script()
        self.assertIn("locked: skipped, a step failed", out)
        self.assertEqual(self.commits(app), 1)
        self.assertEqual(git(app, "status", "--porcelain", env=self.env), "")
        self.assertEqual(self.read(app, "a.md"), "see CONTEXT.md\n")
        self.assertTrue(os.path.exists(os.path.join(app, "CONTEXT.md")))

    def test_a_name_clash_skips_the_project_unchanged(self):
        app = self.repo("clash", {"CONTEXT.md": "old\n", "GLOSSARY.md": "already here\n"})
        before = self.snapshot(app)
        out = self.run_script()
        self.assertEqual(self.snapshot(app), before)
        self.assertIn("clash: skipped", out)
        self.assertIn("GLOSSARY.md", out)

    def test_a_folder_that_is_not_a_git_repo_is_skipped(self):
        loose = os.path.join(self.root, "loose")
        self.write(loose, {"CONTEXT.md": "glossary\n"})
        out = self.run_script()
        self.assertTrue(os.path.exists(os.path.join(loose, "CONTEXT.md")))
        self.assertIn("loose: skipped, not a git repo", out)


class NeverPushes(Scratch):

    def test_the_remote_is_unchanged(self):
        bare = os.path.join(self._tmp.name, "app.git")
        git(self._tmp.name, "init", "-q", "--bare", bare, env=self.env)
        app = self.repo("app", {"CONTEXT.md": "glossary\n"}, remote=bare)
        git(app, "push", "-q", "origin", "main", env=self.env)
        pushed = git(bare, "rev-parse", "main", env=self.env)
        self.run_script()
        self.assertEqual(git(bare, "rev-parse", "main", env=self.env), pushed)
        self.assertEqual(self.commits(app), 2)


if __name__ == "__main__":
    unittest.main()
