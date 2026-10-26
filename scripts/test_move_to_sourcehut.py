#!/usr/bin/env python3
"""Tests for scripts/move-to-sourcehut.py, the move of private repos to SourceHut (shyrosa#115).

Each test drives the command from outside over a scratch dev root and reads what the
run left on disk and in git. Nothing reaches the network: local bare repos stand in
for SourceHut and GitHub, reached through git's `insteadOf` from the real-looking
remote URLs, and fake `hut` and `gh` commands on PATH answer for the two hosts.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "move-to-sourcehut.py")
_spec = importlib.util.spec_from_file_location("move_to_sourcehut", _SCRIPT)
mts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mts)
# The address lives in fleet-references and not here, since scripts/ is exported.
# That file never ships, so in the public repo the tests that need it skip.
HAVE_REFERENCES = os.path.exists(mts.REFERENCES)
SOURCEHUT_EMAIL = None
if HAVE_REFERENCES:
    with open(mts.REFERENCES) as _f:
        SOURCEHUT_EMAIL = mts.sourcehut_address(_f.read())
NOREPLY = "7592333+omarzd@users.noreply.github.com"

# `hut git show <name>` prints the repo's URL, a blank line and `<name> (<visibility>)`,
# as hut's git.go does, when the repo exists; a repo with no visibility file is public,
# hut's default. `hut git create <name> --visibility <v>` makes it as a bare repo.
# Every call is logged.
FAKE_HUT = """#!/bin/sh
echo "$*" >> "$FAKE_ROOT/hut.log"
[ "$1" = git ] || exit 2
case "$2" in
  show)
    [ -d "$FAKE_ROOT/srht/$3" ] || { echo "no such repository \"$3\"" >&2; exit 1; }
    v=public; [ -f "$FAKE_ROOT/srht/$3.visibility" ] && v=$(cat "$FAKE_ROOT/srht/$3.visibility")
    printf 'https://git.sr.ht/~omarzd/%s\n\n\033[1m%s\033[0m (\033[31m%s\033[0m)\n' "$3" "$3" "$v" ;;
  create)
    git init -q --bare "$FAKE_ROOT/srht/$3" && echo "$5" > "$FAKE_ROOT/srht/$3.visibility" &&
      echo "git@git.sr.ht:~omarzd/$3" ;;
  *) exit 2 ;;
esac
"""
# `gh repo view <owner>/<name> --json visibility -q .visibility` prints the visibility
# a test wrote beside the bare repo, or fails as gh does for a missing repo. With a
# gh-down file present it fails the way it does when it cannot reach GitHub.
FAKE_GH = """#!/bin/sh
[ "$1 $2" = "repo view" ] || exit 2
if [ -f "$FAKE_ROOT/gh-down" ]; then echo "error connecting to api.github.com" >&2; exit 1; fi
f="$FAKE_ROOT/github/$3.visibility"
if [ -f "$f" ]; then cat "$f"; else echo "Could not resolve to a Repository" >&2; exit 1; fi
"""


def git(cwd, *args, env=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


@unittest.skipUnless(HAVE_REFERENCES, "fleet-references stays in the private repo")
class Scratch(unittest.TestCase):
    """A dev root, a stand-in SourceHut and GitHub, and fakes for hut and gh."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = self.tmp = os.path.realpath(self._tmp.name)
        self.srht = os.path.join(tmp, "srht")
        self.github = os.path.join(tmp, "github")
        os.makedirs(os.path.join(self.github, "omarzd"))
        os.makedirs(os.path.join(self.github, "mattpocock"))
        os.makedirs(self.srht)
        gitconfig = os.path.join(tmp, "gitconfig")
        with open(gitconfig, "w") as f:
            # Someone else's identity, so the test proves the script sets its own.
            f.write("[user]\n\tname = Not The Manager\n\temail = wrong@example.com\n"
                    "[init]\n\tdefaultBranch = main\n"
                    f'[url "{self.github}/"]\n\tinsteadOf = git@github.com:\n'
                    f'[url "{self.srht}/"]\n\tinsteadOf = git@git.sr.ht:~omarzd/\n')
        bin_dir = self.bin_dir = os.path.join(tmp, "bin")
        os.makedirs(bin_dir)
        for name, body in (("hut", FAKE_HUT), ("gh", FAKE_GH)):
            path = os.path.join(bin_dir, name)
            with open(path, "w") as f:
                f.write(body)
            os.chmod(path, 0o755)
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=gitconfig, GIT_CONFIG_NOSYSTEM="1",
                        GIT_ALLOW_PROTOCOL="file",
                        FAKE_ROOT=tmp, PATH=bin_dir + os.pathsep + os.environ["PATH"])
        for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            self.env.pop(k, None)
        self.root = os.path.join(tmp, "dev")
        os.makedirs(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def project(self, name, origin=None, readme="# hello\n"):
        """A project under the dev root, committed once, with `origin` if given."""
        path = os.path.join(self.root, name)
        os.makedirs(path)
        git(path, "init", "-q", env=self.env)
        with open(os.path.join(path, "README.md"), "w") as f:
            f.write(readme)
        git(path, "add", "-A", env=self.env)
        git(path, "commit", "-qm", "start", env=self.env)
        if origin:
            git(path, "remote", "add", "origin", origin, env=self.env)
        return path

    def on_github(self, owner_repo, visibility, source=None):
        """A bare GitHub stand-in at `owner/repo`, holding `source`'s main if given."""
        bare = os.path.join(self.github, owner_repo + ".git")
        git(self.tmp, "init", "-q", "--bare", bare, env=self.env)
        with open(os.path.join(self.github, owner_repo + ".visibility"), "w") as f:
            f.write(visibility + "\n")
        if source:
            git(source, "push", "-q", bare, "main", env=self.env)
        return bare

    def on_sourcehut(self, name, visibility, source=None):
        """A SourceHut repo another machine made, holding `source`'s main if given."""
        bare = os.path.join(self.srht, name)
        git(self.tmp, "init", "-q", "--bare", bare, env=self.env)
        with open(bare + ".visibility", "w") as f:
            f.write(visibility + "\n")
        if source:
            git(source, "push", "-q", bare, "main", env=self.env)
        return bare

    def without(self, command):
        """PATH holds only the fakes, git and cat, less `command`, so no real hut or gh
        on this machine can stand in for the missing one."""
        only = os.path.join(self.tmp, "bin-without-" + command)
        os.makedirs(only)
        for name in ("hut", "gh"):
            if name != command:
                os.symlink(os.path.join(self.bin_dir, name), os.path.join(only, name))
        for name in ("git", "cat"):
            os.symlink(shutil.which(name, path=os.environ["PATH"]), os.path.join(only, name))
        self.env["PATH"] = only

    def private_on_github(self, name, repo=None):
        """A project whose origin is a private GitHub repo holding its main."""
        repo = repo or name
        path = self.project(name, f"git@github.com:omarzd/{repo}.git")
        self.on_github(f"omarzd/{repo}", "PRIVATE", path)
        return path

    def run_script(self, *flags):
        r = subprocess.run([sys.executable, _SCRIPT, self.root, *flags], capture_output=True,
                           text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def hut_calls(self):
        path = os.path.join(self.tmp, "hut.log")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return f.read().splitlines()

    def config(self, path, key):
        r = subprocess.run(["git", "config", "--local", "--get", key], cwd=path,
                           capture_output=True, text=True, env=self.env)
        return r.stdout.strip() or None

    def snapshot(self, path):
        """Every file under `path` as bytes: proof a run left it alone."""
        seen = {}
        for folder, _, names in os.walk(path):
            for name in names:
                full = os.path.join(folder, name)
                with open(full, "rb") as f:
                    seen[os.path.relpath(full, path)] = f.read()
        return seen

    def heads(self, bare):
        return git(bare, "for-each-ref", "--format=%(refname) %(objectname)",
                   "refs/heads", env=self.env)


class TheAddress(unittest.TestCase):

    def test_it_comes_from_the_sourcehut_section_alone(self):
        text = ("## GitHub\n\nuse `omarzd <noreply@example.com>`\n\n"
                "## A SourceHut repo commits as this\n\nas `omarzd <hut@example.com>`, "
                "not <later@example.com>\n\n## Other\n\n<other@example.com>\n")
        self.assertEqual(mts.sourcehut_address(text), "hut@example.com")

    def test_none_without_a_sourcehut_heading(self):
        self.assertIsNone(mts.sourcehut_address("## GitHub\n\n<noreply@example.com>\n"))

    @unittest.skipUnless(HAVE_REFERENCES, "fleet-references stays in the private repo")
    def test_the_real_file_names_one(self):
        self.assertRegex(SOURCEHUT_EMAIL or "", r"^[^@\s]+@[^@\s]+$")


class TheMove(Scratch):

    def test_a_github_origin_with_credentials_moves_without_printing_them(self):
        origin = "https://fake-token-129@github.com/omarzd/x.git"
        path = self.project("x", origin)
        bare = self.on_github("omarzd/x", "PRIVATE", path)
        git(path, "config", f"url.{bare}.insteadOf", origin, env=self.env)
        out = self.run_script("--push")
        self.assertEqual(self.config(path, "remote.origin.url"), "git@git.sr.ht:~omarzd/x")
        self.assertEqual(self.config(path, "remote.github.url"), origin)
        self.assertNotIn("fake-token-129", out)
        self.assertIn("x: origin -> git@git.sr.ht:~omarzd/x", out)
        self.assertIn(mts.readme_line("x"), git(bare, "show", "main:README.md", env=self.env))
        before = (self.snapshot(path), self.snapshot(bare))
        self.assertIn("nothing to do", self.run_script("--push"))
        self.assertEqual((self.snapshot(path), self.snapshot(bare)), before)

    def test_https_and_ssh_url_origins_still_move_and_push(self):
        for index, origin in enumerate((
                "https://github.com/omarzd/x.git",
                "ssh://git@github.com/omarzd/x.git",
                "https://fake-user-129:fake-pass%40word-129@github.com/omarzd/x.git")):
            with self.subTest(origin=origin):
                origin = origin.replace("/x.git", f"/x{index}.git")
                path = self.project(f"x{index}", origin)
                bare = self.on_github(f"omarzd/x{index}", "PRIVATE", path)
                git(path, "config", f"url.{bare}.insteadOf", origin, env=self.env)
                out = self.run_script("--push")
                self.assertEqual(self.config(path, "remote.origin.url"),
                                 f"git@git.sr.ht:~omarzd/x{index}")
                self.assertNotIn("fake-", out)

    def test_a_private_repo_with_a_public_twin_moves_to_its_private_name(self):
        path = self.private_on_github("shyrosa", repo="shyrosa-private")
        self.on_github("omarzd/shyrosa", "PUBLIC")
        out = self.run_script()
        self.assertIn("git create shyrosa-private --visibility private", self.hut_calls())
        self.assertTrue(os.path.isdir(os.path.join(self.srht, "shyrosa-private")))
        self.assertEqual(self.config(path, "remote.origin.url"),
                         "git@git.sr.ht:~omarzd/shyrosa-private")
        self.assertEqual(self.config(path, "remote.github.url"),
                         "git@github.com:omarzd/shyrosa-private.git")
        self.assertIn("shyrosa:", out)

    def test_a_private_repo_without_a_twin_keeps_its_plain_name(self):
        path = self.private_on_github("notes")
        self.run_script()
        self.assertIn("git create notes --visibility private", self.hut_calls())
        self.assertEqual(self.config(path, "remote.origin.url"), "git@git.sr.ht:~omarzd/notes")

    def test_a_private_twin_does_not_count_as_public(self):
        self.private_on_github("tool", repo="tool-work")
        self.on_github("omarzd/tool", "PRIVATE")
        self.run_script()
        self.assertIn("git create tool --visibility private", self.hut_calls())

    def test_the_repo_commits_as_the_sourcehut_address(self):
        path = self.private_on_github("notes")
        self.run_script()
        self.assertEqual(self.config(path, "user.email"), SOURCEHUT_EMAIL)
        self.assertEqual(self.config(path, "user.name"), "omarzd")

    def test_a_project_never_pushed_gets_a_repo_and_no_github_remote(self):
        path = self.project("sketch")
        self.run_script()
        self.assertIn("git create sketch --visibility private", self.hut_calls())
        self.assertEqual(self.config(path, "remote.origin.url"), "git@git.sr.ht:~omarzd/sketch")
        self.assertIsNone(self.config(path, "remote.github.url"))
        self.assertEqual(self.config(path, "user.email"), SOURCEHUT_EMAIL)

    def test_a_repo_another_machine_already_made_is_not_made_again(self):
        path = self.private_on_github("notes")
        self.on_sourcehut("notes", "private")
        self.run_script()
        self.assertNotIn("git create notes --visibility private", self.hut_calls())
        self.assertEqual(self.config(path, "remote.origin.url"), "git@git.sr.ht:~omarzd/notes")

    def test_a_repo_another_machine_pushed_the_same_history_to_is_used(self):
        path = self.private_on_github("notes")
        bare = self.on_sourcehut("notes", "private", path)
        with open(os.path.join(path, "more.txt"), "w") as f:
            f.write("more\n")
        git(path, "add", "-A", env=self.env)
        git(path, "commit", "-qm", "more", env=self.env)
        self.run_script("--push")
        self.assertEqual(git(bare, "rev-parse", "main", env=self.env),
                         git(path, "rev-parse", "main", env=self.env))


class WhatItLeavesAlone(Scratch):

    def test_other_hosts_are_reported_without_url_credentials(self):
        for name, origin in (
                ("overleaf", "https://fake-user-129:fake-password-129@git.overleaf.com/abc"),
                ("token", "https://fake-token-129@git.overleaf.com/def")):
            self.project(name, origin)
        out = self.run_script()
        self.assertNotIn("fake-", out)
        self.assertIn("origin https://git.overleaf.com/abc is on neither", out)
        self.assertIn("origin https://git.overleaf.com/def is on neither", out)

    def test_a_moved_projects_invalid_github_remote_hides_credentials(self):
        path = self.project("notes", "git@git.sr.ht:~omarzd/notes")
        git(path, "remote", "add", "github",
            "https://fake-token-129@git.overleaf.com/abc", env=self.env)
        out = self.run_script("--push")
        self.assertNotIn("fake-token-129", out)
        self.assertIn("its github remote https://git.overleaf.com/abc is not omarzd's", out)

    def test_command_errors_hide_all_url_userinfo(self):
        self.private_on_github("notes")
        diagnostic = ("https://fake-token-129@github.com/omarzd/notes.git and "
                      "https://fake-user-129:fake-password-129@git.overleaf.com/abc")
        for command in ("gh", "hut"):
            with self.subTest(command=command):
                executable = os.path.join(self.bin_dir, command)
                with open(executable) as f:
                    original = f.read()
                try:
                    with open(executable, "w") as f:
                        f.write(f"#!/bin/sh\necho '{diagnostic}' >&2\nexit 1\n")
                    out = self.run_script()
                    self.assertNotIn("fake-", out)
                    self.assertIn("https://github.com/omarzd/notes.git and "
                                  "https://git.overleaf.com/abc", out)
                finally:
                    with open(executable, "w") as f:
                        f.write(original)

    def test_git_stderr_hides_url_userinfo(self):
        path = self.private_on_github("notes")
        self.run_script()
        executable = os.path.join(self.bin_dir, "uploadpack")
        with open(executable, "w") as f:
            f.write("#!/bin/sh\necho 'fatal: https://fake-token-129@github.com/omarzd/notes.git' "
                    ">&2\nexit 1\n")
        os.chmod(executable, 0o755)
        git(path, "config", "remote.github.uploadpack", executable, env=self.env)
        out = self.run_script("--push")
        self.assertNotIn("fake-token-129", out)
        self.assertIn("git ls-remote --symref failed", out)
        self.assertIn("fatal: https://github.com/omarzd/notes.git", out)

    def assert_untouched(self, name, out, reason):
        self.assertIn(f"{name}: skipped, {reason}", out)
        self.assertFalse(any(name in call for call in self.hut_calls()))

    def test_a_clone_of_someone_elses_repo_is_skipped_untouched(self):
        path = self.project("matt-skills", "https://github.com/mattpocock/skills.git")
        before = self.snapshot(path)
        out = self.run_script("--push")
        self.assert_untouched("matt-skills", out, "a clone of someone else's repo")
        self.assertEqual(self.snapshot(path), before)

    def test_a_clone_from_another_sourcehut_user_is_skipped(self):
        self.project("hut", "https://git.sr.ht/~xenrox/hut")
        out = self.run_script()
        self.assert_untouched("hut", out, "a clone of someone else's repo")

    def test_a_public_repo_stays_on_github(self):
        path = self.project("CudaSwallow", "git@github.com:omarzd/CudaSwallow.git")
        self.on_github("omarzd/CudaSwallow", "PUBLIC", path)
        before = self.snapshot(path)
        out = self.run_script("--push")
        self.assert_untouched("CudaSwallow", out, "public, stays on GitHub")
        self.assertEqual(self.snapshot(path), before)

    def test_a_repo_github_cannot_find_is_skipped(self):
        self.project("gone", "git@github.com:omarzd/gone.git")
        out = self.run_script()
        self.assertIn("gone: skipped, origin omarzd/gone is not on GitHub", out)

    def test_gh_failing_skips_rather_than_guessing_no_twin(self):
        path = self.project("sketch")
        open(os.path.join(self.tmp, "gh-down"), "w").close()
        before = self.snapshot(path)
        out = self.run_script()
        self.assertIn("sketch: skipped, gh could not read omarzd/sketch", out)
        self.assertEqual(self.hut_calls(), [])
        self.assertEqual(self.snapshot(path), before)

    def test_origin_on_another_host_is_named_as_such(self):
        self.project("lab", "git@gitlab.com:omarzd/lab.git")
        out = self.run_script()
        self.assertIn("lab: skipped, origin git@gitlab.com:omarzd/lab.git is on neither", out)

    def test_an_unreachable_sourcehut_skips_one_project_not_the_run(self):
        self.private_on_github("notes")
        self.project("sketch")
        os.makedirs(os.path.join(self.srht, "notes"))  # not a repo: ls-remote fails
        with open(os.path.join(self.srht, "notes.visibility"), "w") as f:
            f.write("private\n")
        out = self.run_script()
        self.assertIn("notes: skipped, git ls-remote", out)
        self.assertIn("sketch: origin -> git@git.sr.ht:~omarzd/sketch", out)

    def test_a_folder_that_is_not_a_repo_is_skipped(self):
        os.makedirs(os.path.join(self.root, "loose"))
        out = self.run_script()
        self.assertIn("loose: skipped, not a git repo", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "loose", ".git")))

    def test_an_existing_sourcehut_repo_that_is_not_private_is_skipped(self):
        path = self.private_on_github("notes")
        self.on_sourcehut("notes", "unlisted")
        before = self.snapshot(path)
        out = self.run_script("--push")
        self.assertIn("notes: skipped, SourceHut repo notes is not private", out)
        self.assertEqual(self.snapshot(path), before)

    def test_an_existing_sourcehut_repo_with_unrelated_history_is_skipped(self):
        # Other content, so the two first commits cannot come out as one commit.
        other = self.project("elsewhere-notes", readme="# another notes\n")
        bare = self.on_sourcehut("notes", "private", other)
        shutil.rmtree(other)
        path = self.private_on_github("notes")
        before = (self.snapshot(path), self.snapshot(bare))
        out = self.run_script("--push")
        self.assertIn("notes: skipped, SourceHut repo notes shares no history with it", out)
        self.assertEqual((self.snapshot(path), self.snapshot(bare)), before)

    def test_a_moved_project_whose_github_remote_is_public_gets_no_readme_push(self):
        path = self.project("notes", "git@git.sr.ht:~omarzd/notes")
        self.on_sourcehut("notes", "private")
        git(path, "remote", "add", "github", "git@github.com:omarzd/notes.git", env=self.env)
        bare = self.on_github("omarzd/notes", "PUBLIC", path)
        before = self.snapshot(bare)
        out = self.run_script("--push")
        self.assertIn("notes: skipped, its github remote omarzd/notes is not private", out)
        self.assertEqual(self.snapshot(bare), before)

    def test_a_moved_project_whose_github_remote_is_someone_elses_is_skipped(self):
        path = self.project("notes", "git@git.sr.ht:~omarzd/notes")
        self.on_sourcehut("notes", "private")
        git(path, "remote", "add", "github", "git@github.com:mattpocock/notes.git", env=self.env)
        out = self.run_script("--push")
        self.assertIn("notes: skipped, its github remote "
                      "git@github.com:mattpocock/notes.git is not omarzd's", out)

    def test_a_missing_hut_skips_the_project_not_the_run(self):
        self.project("sketch")
        self.without("hut")
        out = self.run_script()
        self.assertIn("sketch: skipped, hut", out)
        self.assertIn("move-to-sourcehut: nothing to do, skipped 1", out)

    def test_a_missing_gh_skips_the_project_not_the_run(self):
        self.private_on_github("notes")
        self.without("gh")
        out = self.run_script()
        self.assertIn("notes: skipped, gh", out)

    def test_a_git_failure_while_setting_remotes_skips_the_project_not_the_run(self):
        path = self.private_on_github("notes")
        self.project("sketch")
        open(os.path.join(path, ".git", "config.lock"), "w").close()  # git config cannot write
        out = self.run_script()
        self.assertIn("notes: skipped, git", out)
        self.assertIn("sketch: origin -> git@git.sr.ht:~omarzd/sketch", out)

    def test_a_folder_inside_another_repo_is_skipped(self):
        git(self.root, "init", "-q", env=self.env)
        os.makedirs(os.path.join(self.root, "loose"))
        out = self.run_script()
        self.assertIn(f"loose: skipped, not its own git repo, it sits inside {self.root}", out)
        self.assertEqual(self.hut_calls(), [])

    def test_a_taken_github_remote_name_is_skipped(self):
        path = self.private_on_github("notes")
        git(path, "remote", "add", "github", "git@github.com:omarzd/other.git", env=self.env)
        out = self.run_script()
        self.assertIn("notes: skipped, it already has a remote named github", out)
        self.assertEqual(self.hut_calls(), [])

    def test_a_github_remote_matching_origin_is_skipped_not_left_on_github(self):
        path = self.private_on_github("notes")
        git(path, "remote", "add", "github", "git@github.com:omarzd/notes.git", env=self.env)
        out = self.run_script("--push")
        self.assertIn("notes: skipped, it already has a remote named github", out)
        self.assertEqual(self.config(path, "remote.origin.url"), "git@github.com:omarzd/notes.git")


class Pushing(Scratch):

    def test_without_the_push_switch_nothing_is_pushed(self):
        self.private_on_github("notes")
        github_before = self.snapshot(os.path.join(self.github, "omarzd", "notes.git"))
        out = self.run_script()
        self.assertEqual(self.heads(os.path.join(self.srht, "notes")), "")
        self.assertEqual(self.snapshot(os.path.join(self.github, "omarzd", "notes.git")),
                         github_before)
        self.assertIn("notes: not pushed", out)

    def test_the_push_switch_carries_every_branch_and_tag_to_sourcehut(self):
        path = self.private_on_github("notes")
        git(path, "branch", "side", env=self.env)
        git(path, "tag", "-a", "v1", "-m", "one", env=self.env)
        self.run_script("--push")
        bare = os.path.join(self.srht, "notes")
        self.assertEqual(self.heads(bare), self.heads(os.path.join(path, ".git")))
        self.assertEqual(git(bare, "rev-parse", "v1", env=self.env),
                         git(path, "rev-parse", "v1", env=self.env))
        self.assertEqual(self.config(path, "branch.main.remote"), "origin")

    def test_the_github_copy_gets_one_readme_line_and_the_local_tree_does_not(self):
        path = self.private_on_github("notes")
        self.run_script("--push")
        bare = os.path.join(self.github, "omarzd", "notes.git")
        readme = git(bare, "show", "main:README.md", env=self.env)
        self.assertEqual(readme.count("https://git.sr.ht/~omarzd/notes"), 1)
        self.assertTrue(readme.startswith("# hello\n"))
        self.assertEqual(git(bare, "log", "-1", "--format=%ae", "main", env=self.env), NOREPLY)
        with open(os.path.join(path, "README.md")) as f:
            self.assertEqual(f.read(), "# hello\n")
        self.assertEqual(git(path, "status", "--porcelain", env=self.env), "")

    def readme_project(self, files):
        """A private GitHub project whose tree holds `files` and no other."""
        path = self.project("notes", "git@github.com:omarzd/notes.git")
        git(path, "rm", "-q", "README.md", env=self.env)
        for rel, data in files.items():
            with open(os.path.join(path, rel), "wb") as f:
                f.write(data)
        git(path, "add", "-A", env=self.env)
        git(path, "commit", "-qm", "readmes", env=self.env)
        return path, self.on_github("omarzd/notes", "PRIVATE", path)

    def test_the_line_goes_into_readme_md_not_a_translation_beside_it(self):
        path, bare = self.readme_project({"README-ja.md": b"# ja\n", "README.md": b"# en\n"})
        self.run_script("--push")
        self.assertIn(mts.readme_line("notes"), git(bare, "show", "main:README.md", env=self.env))
        self.assertEqual(git(bare, "show", "main:README-ja.md", env=self.env), "# ja")

    def test_a_binary_readme_lookalike_is_not_taken_for_the_readme(self):
        path, bare = self.readme_project({"README.assets.png": b"\x89PNG\r\n\x1a\n\xff\x00"})
        out = self.run_script("--push")
        self.assertIn(mts.readme_line("notes"), git(bare, "show", "main:README.md", env=self.env))
        self.assertIn("notes: added the SourceHut line to README.md on GitHub", out)

    def test_a_readme_that_is_not_utf8_skips_the_project_not_the_run(self):
        path, bare = self.readme_project({"README.md": b"caf\xe9\n"})
        self.project("sketch")
        out = self.run_script("--push")
        self.assertIn("notes: skipped, README.md on GitHub is not UTF-8 text", out)
        self.assertIn("sketch: origin -> git@git.sr.ht:~omarzd/sketch", out)

    def test_a_github_copy_without_a_readme_gets_one(self):
        path = self.project("bare-notes", "git@github.com:omarzd/bare-notes.git")
        git(path, "rm", "-q", "README.md", env=self.env)
        with open(os.path.join(path, "x.txt"), "w") as f:
            f.write("x\n")
        git(path, "add", "-A", env=self.env)
        git(path, "commit", "-qm", "no readme", env=self.env)
        bare = self.on_github("omarzd/bare-notes", "PRIVATE", path)
        self.run_script("--push")
        self.assertIn("https://git.sr.ht/~omarzd/bare-notes",
                      git(bare, "show", "main:README.md", env=self.env))

    def test_a_second_run_changes_nothing(self):
        self.private_on_github("notes")
        self.project("sketch")
        self.run_script("--push")
        before = (self.snapshot(self.root), self.snapshot(self.srht), self.snapshot(self.github))
        calls = len(self.hut_calls())
        out = self.run_script("--push")
        self.assertEqual((self.snapshot(self.root), self.snapshot(self.srht),
                          self.snapshot(self.github)), before)
        self.assertEqual(len([c for c in self.hut_calls()[calls:] if "create" in c]), 0)
        self.assertIn("nothing to do", out)
        self.assertNotIn("not pushed", out)

    def test_a_run_without_push_after_a_full_push_says_nothing_waits(self):
        self.private_on_github("notes")
        self.run_script("--push")
        out = self.run_script()
        self.assertNotIn("not pushed", out)
        self.assertIn("nothing to do", out)

    def test_another_repos_url_in_the_readme_does_not_count_as_the_line(self):
        path = self.project("notes", "git@github.com:omarzd/notes.git",
                            readme="# hello\n\nSee https://git.sr.ht/~omarzd/notes-private\n")
        bare = self.on_github("omarzd/notes", "PRIVATE", path)
        self.run_script("--push")
        self.assertIn(mts.readme_line("notes"), git(bare, "show", "main:README.md", env=self.env))

    def test_a_second_run_without_push_after_a_first_without_push_is_idle(self):
        self.private_on_github("notes")
        self.run_script()
        before = (self.snapshot(self.root), self.snapshot(self.srht), self.snapshot(self.github))
        out = self.run_script()
        self.assertEqual((self.snapshot(self.root), self.snapshot(self.srht),
                          self.snapshot(self.github)), before)
        self.assertIn("notes: not pushed, waits for --push", out)
        self.assertIn("move-to-sourcehut: nothing changed, 1 project(s) wait for --push, "
                      "skipped 0", out)
        self.assertNotIn("nothing to do", out)


if __name__ == "__main__":
    unittest.main()
