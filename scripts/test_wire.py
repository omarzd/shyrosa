#!/usr/bin/env python3
"""Tests for wire.sh.

Each test runs wire.sh with HOME set to a temp dir and reads what it left there.
Besides the skills, wire.sh links three fleet files into ~/.claude: the fleet
settings, the status-line script and the Unslop style (shyrosa#99). A real file
already in one of those places is renamed aside, never deleted.

The settings link turns auto-memory off, so its first link waits for
--link-settings; a plain run only keeps a settings link that is already there
(shyrosa#99, gate round 1).

Matt's skills load from upstream/, linked the same way as the overlays, and a
link into an old Matt clone for a skill that is gone is removed (shyrosa#106).

Every link is checked after it is made; an ln that copies instead, as on Windows
outside Developer Mode, stops the run with the path named (shyrosa#113).
Real skill folders and ~/.shyrosa move to .pre-fleet before retrying the link,
so a copying ln stops again on the second run. A taken backup remains a SKIP
and leaves both paths untouched (shyrosa#125).

Codex gets fleet/codex/AGENTS.md and every successfully linked Claude skill.
Its real targets use the same move-aside behavior, and only stale links resolving
into this checkout are removed (shyrosa#127).
"""
import os
import shutil
import subprocess
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
WIRE = os.path.join(REPO, "wire.sh")

FLEET = {
    "settings.json": "fleet/settings.json",
    "statusline-context.py": "fleet/statusline-context.py",
    "output-styles/unslop.md": "fleet/unslop.md",
}
ASIDE = ".pre-fleet"
FLAG = "--link-settings"


def run_wire(script, home, *args, **env_extra):
    env = dict(os.environ, HOME=home, **env_extra)
    return subprocess.run(["bash", script, *args], env=env, capture_output=True, text=True)


def snapshot(root):
    """Every link and file under root, as (kind, target-or-content)."""
    seen = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            if os.path.islink(path):
                seen[rel] = ("link", os.readlink(path))
            elif os.path.isfile(path):
                with open(path, "rb") as f:
                    seen[rel] = ("file", f.read())
    return seen


class Wire(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.claude = os.path.join(self.home, ".claude")

    def tearDown(self):
        self._tmp.cleanup()

    def wire(self, *args):
        r = run_wire(WIRE, self.home, *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def put(self, rel, data):
        path = os.path.join(self.claude, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(data)

    def read(self, rel):
        with open(os.path.join(self.claude, rel)) as f:
            return f.read()

    def assertLinkedIntoRepo(self, rel):
        path = os.path.join(self.claude, rel)
        self.assertTrue(os.path.islink(path), rel)
        self.assertEqual(os.readlink(path), os.path.join(REPO, FLEET[rel]))

    def test_links_the_three_fleet_files_into_the_repo(self):
        self.wire(FLAG)
        for rel in FLEET:
            self.assertLinkedIntoRepo(rel)

    def test_a_plain_run_links_the_status_line_and_style_but_not_settings(self):
        self.wire()
        self.assertLinkedIntoRepo("statusline-context.py")
        self.assertLinkedIntoRepo("output-styles/unslop.md")
        self.assertFalse(os.path.lexists(os.path.join(self.claude, "settings.json")))

    def test_a_plain_run_leaves_a_real_settings_file_alone_and_says_so(self):
        self.put("settings.json", '{"theme": "light"}\n')
        last = self.wire().splitlines()[-1]
        path = os.path.join(self.claude, "settings.json")
        self.assertFalse(os.path.islink(path))
        self.assertEqual(self.read("settings.json"), '{"theme": "light"}\n')
        self.assertFalse(os.path.lexists(path + ASIDE))
        self.assertIn("2 fleet files linked", last)
        self.assertIn("settings.json not linked", last)
        self.assertIn(FLAG, last)

    def test_a_plain_run_leaves_a_link_elsewhere_alone(self):
        os.makedirs(self.claude)
        path = os.path.join(self.claude, "settings.json")
        os.symlink("/elsewhere/settings.json", path)
        self.wire()
        self.assertEqual(os.readlink(path), "/elsewhere/settings.json")

    def test_the_flag_renames_a_real_settings_file_aside_and_links_it(self):
        self.put("settings.json", '{"theme": "light"}\n')
        self.wire(FLAG)
        self.assertLinkedIntoRepo("settings.json")
        self.assertEqual(self.read("settings.json" + ASIDE), '{"theme": "light"}\n')

    def test_a_plain_run_after_the_flag_keeps_the_settings_link(self):
        self.put("settings.json", '{"theme": "light"}\n')
        self.wire(FLAG)
        first = snapshot(self.home)
        last = self.wire().splitlines()[-1]
        self.assertLinkedIntoRepo("settings.json")
        self.assertEqual(snapshot(self.home), first)
        self.assertIn("3 fleet files linked", last)

    def test_a_real_style_file_is_renamed_aside(self):
        self.put("output-styles/unslop.md", "old style\n")
        self.wire()
        self.assertLinkedIntoRepo("output-styles/unslop.md")
        self.assertEqual(self.read("output-styles/unslop.md" + ASIDE), "old style\n")

    def test_an_old_link_is_replaced(self):
        os.makedirs(self.claude)
        os.symlink("/nowhere/statusline-context.py", os.path.join(self.claude, "statusline-context.py"))
        self.wire()
        self.assertLinkedIntoRepo("statusline-context.py")

    def test_a_taken_aside_name_is_never_written_over(self):
        self.put("settings.json", "current\n")
        self.put("settings.json" + ASIDE, "older\n")
        out = self.wire(FLAG)
        self.assertEqual(self.read("settings.json"), "current\n")
        self.assertEqual(self.read("settings.json" + ASIDE), "older\n")
        self.assertIn("2 fleet files linked, 1 skipped", out.splitlines()[-1])

    def test_a_second_run_changes_nothing(self):
        self.put("settings.json", '{"theme": "light"}\n')
        self.wire(FLAG)
        first = snapshot(self.home)
        self.wire(FLAG)
        self.assertEqual(snapshot(self.home), first)

    def test_the_skills_are_linked_as_before(self):
        self.wire()
        self.wire()
        skills = sorted(n for n in os.listdir(os.path.join(REPO, "overlay"))
                        if os.path.isdir(os.path.join(REPO, "overlay", n)))
        self.assertTrue(skills)
        for name in skills:
            path = os.path.join(self.claude, "skills", name)
            self.assertEqual(os.readlink(path), os.path.join(REPO, "overlay", name))

    def test_done_line_counts_the_fleet_files_beside_the_skills(self):
        last = self.wire(FLAG).splitlines()[-1]
        self.assertIn("3 fleet files linked", last)
        self.assertIn("skills wired", last)


def skill_dirs(root):
    return sorted(n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n)))


class ScratchRepo(unittest.TestCase):
    """wire.sh copied into a scratch repo with a made-up overlay/ and upstream/,
    so each case holds whatever the real vendored copy happens to hold today."""

    OVERLAYS = ("ours", "shared")
    UPSTREAM = ("tdd", "shared", "implement-spec")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(os.path.realpath(self._tmp.name), "repo")
        self.home = os.path.join(self._tmp.name, "home")
        self.skills = os.path.join(self.home, ".claude", "skills")
        os.makedirs(self.skills)
        os.makedirs(self.repo)
        shutil.copy(WIRE, os.path.join(self.repo, "wire.sh"))
        for rel in FLEET.values():
            path = os.path.join(self.repo, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
        os.makedirs(os.path.join(self.repo, "fleet", "codex"))
        with open(os.path.join(self.repo, "fleet", "codex", "AGENTS.md"), "w") as f:
            f.write("synthetic fleet instructions\n")
        for top, names in (("overlay", self.OVERLAYS), ("upstream", self.UPSTREAM)):
            for name in names:
                os.makedirs(os.path.join(self.repo, top, name))

    def tearDown(self):
        self._tmp.cleanup()

    def run_wire(self):
        r = run_wire(os.path.join(self.repo, "wire.sh"), self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def wire(self):
        return self.run_wire().stdout

    def link(self, name, target):
        os.symlink(target, os.path.join(self.skills, name))

    def target(self, name):
        return os.readlink(os.path.join(self.skills, name))

    def exists(self, name):
        return os.path.lexists(os.path.join(self.skills, name))

    def assert_home_checkout_stays_usable(self, source):
        source = os.path.realpath(source)
        before = snapshot(source)
        for _ in range(2):
            r = run_wire(os.path.join(source, "wire.sh"), self.home, FLAG)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(os.path.islink(source))
            self.assertFalse(os.path.lexists(source + ASIDE))
            self.assertEqual(snapshot(source), before)
            for rel, path in FLEET.items():
                target = os.path.join(self.home, ".claude", rel)
                self.assertEqual(os.readlink(target), os.path.join(source, path))
                self.assertTrue(os.path.isfile(target), target)
            for name, top in (("ours", "overlay"), ("tdd", "upstream")):
                self.assertEqual(self.target(name), os.path.join(source, top, name))
                self.assertTrue(os.path.isdir(os.path.join(self.skills, name)))
                codex_skill = os.path.join(self.home, ".codex", "skills", name)
                self.assertTrue(os.path.samefile(codex_skill, os.path.join(self.skills, name)))
            agents = os.path.join(self.home, ".codex", "AGENTS.md")
            self.assertEqual(os.readlink(agents), os.path.join(source, "fleet", "codex", "AGENTS.md"))
            self.assertTrue(os.path.isfile(agents))


class Codex(ScratchRepo):
    def codex_path(self, rel):
        path = os.path.join(self.home, ".codex", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def test_links_agents_and_every_successful_claude_skill(self):
        self.wire()
        codex = os.path.join(self.home, ".codex")
        self.assertEqual(os.readlink(os.path.join(codex, "AGENTS.md")),
                         os.path.join(self.repo, "fleet", "codex", "AGENTS.md"))
        self.assertEqual(sorted(os.listdir(os.path.join(codex, "skills"))),
                         ["ours", "shared", "tdd"])
        for name in ("ours", "shared", "tdd"):
            path = os.path.join(codex, "skills", name)
            self.assertEqual(os.readlink(path), self.target(name))
            self.assertTrue(os.path.samefile(path, os.path.join(self.skills, name)))
        before = snapshot(self.home)
        self.wire()
        self.assertEqual(snapshot(self.home), before)

    def test_real_agents_file_and_skill_folder_move_aside_intact(self):
        agents = self.codex_path("AGENTS.md")
        with open(agents, "wb") as f:
            f.write(b"local instructions\x00\xff\n")
        skill = self.codex_path("skills/ours")
        os.makedirs(os.path.join(skill, "empty"))
        with open(os.path.join(skill, "SKILL.md"), "w") as f:
            f.write("local skill\n")
        os.symlink("missing", os.path.join(skill, "local-link"))
        before = snapshot(skill)
        self.wire()
        with open(agents + ASIDE, "rb") as f:
            self.assertEqual(f.read(), b"local instructions\x00\xff\n")
        self.assertEqual(snapshot(skill + ASIDE), before)
        self.assertTrue(os.path.isdir(os.path.join(skill + ASIDE, "empty")))
        self.assertEqual(os.readlink(skill), self.target("ours"))
        self.assertTrue(os.path.isfile(agents))

    def test_occupied_backups_skip_real_targets_and_survive_reruns(self):
        for rel, kind in (("AGENTS.md", "file"), ("skills/ours", "folder"),
                          ("skills/tdd", "link")):
            target = self.codex_path(rel)
            with open(target, "w") as f:
                f.write("current\n")
            if kind == "file":
                with open(target + ASIDE, "w") as f:
                    f.write("backup\n")
            elif kind == "folder":
                os.makedirs(target + ASIDE)
            else:
                os.symlink(os.path.join(self.repo, "gone"), target + ASIDE)
        before = snapshot(os.path.join(self.home, ".codex"))
        for _ in range(2):
            r = self.run_wire()
            after = snapshot(os.path.join(self.home, ".codex"))
            for path, entry in before.items():
                self.assertEqual(after[path], entry)
            self.assertTrue(os.path.isdir(self.codex_path("skills/ours") + ASIDE))
            self.assertIn("1 codex links, 3 skipped", r.stdout.splitlines()[-1])
            self.assertEqual(r.stderr.count("SKIP"), 3)

    def test_stale_owned_links_removed_and_foreign_links_and_backups_preserved(self):
        links = {
            "retired": os.path.join(self.repo, "overlay", "retired"),
            "implement-spec": os.path.join(self.repo, "upstream", "implement-spec"),
            "foreign": "/elsewhere/skill",
            "relative-foreign": "../../.agents/skills/custom",
            "prefix-lookalike": self.repo + "-other/overlay/retired",
            "retired.pre-fleet": os.path.join(self.repo, "overlay", "retired"),
        }
        for name, source in links.items():
            os.symlink(source, self.codex_path("skills/" + name))
        real = self.codex_path("skills/local")
        os.makedirs(real)
        for attempt in range(2):
            last = self.wire().splitlines()[-1]
            for name in ("retired", "implement-spec"):
                self.assertFalse(os.path.lexists(self.codex_path("skills/" + name)))
            for name in set(links) - {"retired", "implement-spec"}:
                self.assertEqual(os.readlink(self.codex_path("skills/" + name)), links[name])
            self.assertTrue(os.path.isdir(real))
            self.assertIn(f"{2 if attempt == 0 else 0} stale codex links removed", last)

    def test_a_skipped_claude_skill_is_not_mirrored_and_its_old_codex_link_is_pruned(self):
        for name in ("ours", "tdd"):
            target = os.path.join(self.skills, name)
            os.makedirs(target)
            os.symlink("missing", target + ASIDE)
        os.symlink(os.path.join(self.repo, "overlay", "ours"), self.codex_path("skills/ours"))
        os.symlink("/foreign/tdd", self.codex_path("skills/tdd"))
        last = self.wire().splitlines()[-1]
        self.assertFalse(os.path.lexists(self.codex_path("skills/ours")))
        self.assertEqual(os.readlink(self.codex_path("skills/tdd")), "/foreign/tdd")
        self.assertIn("2 codex links, 0 skipped, 1 stale codex links removed", last)

    def test_stale_ownership_uses_resolved_paths_including_dangling_links(self):
        owned = self.codex_path("skills/relative-owned")
        os.symlink(os.path.relpath(os.path.join(self.repo, "overlay", "retired"),
                                   os.path.realpath(os.path.dirname(owned))), owned)
        os.symlink(self.repo, self.codex_path("skills/repo-root"))
        foreign = {
            "traversal": self.repo + "/../foreign/retired",
            "indirect": self.repo + "/foreign/retired",
        }
        os.symlink(os.path.join(self._tmp.name, "foreign"), os.path.join(self.repo, "foreign"))
        for name, source in foreign.items():
            os.symlink(source, self.codex_path("skills/" + name))
        last = self.wire().splitlines()[-1]
        self.assertFalse(os.path.lexists(owned))
        self.assertFalse(os.path.lexists(self.codex_path("skills/repo-root")))
        for name, source in foreign.items():
            self.assertEqual(os.readlink(self.codex_path("skills/" + name)), source)
        self.assertIn("2 stale codex links removed", last)

    def test_codex_config_is_untouched(self):
        path = self.codex_path("config.toml")
        with open(path, "w") as f:
            f.write('model = "synthetic-model"\n')
        self.wire()
        with open(path) as f:
            self.assertEqual(f.read(), 'model = "synthetic-model"\n')
        self.assertFalse(os.path.lexists(path + ASIDE))

    def test_no_successful_claude_links_still_wires_agents_and_prunes_stale_skills(self):
        for name in ("ours", "shared", "tdd"):
            target = os.path.join(self.skills, name)
            os.makedirs(target)
            os.symlink("missing", target + ASIDE)
        os.symlink(os.path.join(self.repo, "overlay", "ours"), self.codex_path("skills/ours"))
        r = subprocess.run(["/bin/bash", os.path.join(self.repo, "wire.sh")],
                           env=dict(os.environ, HOME=self.home), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(self.codex_path("AGENTS.md")))
        self.assertEqual(os.listdir(self.codex_path("skills/")), [])
        self.assertIn("1 codex links, 0 skipped, 1 stale codex links removed", r.stdout)


class Skills(ScratchRepo):
    def test_a_checkout_directly_at_the_home_link_stays_usable(self):
        source = os.path.join(self.home, ".shyrosa")
        shutil.move(self.repo, source)
        self.assert_home_checkout_stays_usable(source)

    def test_running_through_the_fleet_link_keeps_it_usable(self):
        home_link = os.path.join(self.home, ".shyrosa")
        os.symlink(self.repo, home_link)
        r = run_wire(os.path.join(home_link, "wire.sh"), self.home, FLAG)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.readlink(home_link), os.path.realpath(self.repo))
        self.assertTrue(os.path.isfile(os.path.join(home_link, "wire.sh")))
        for rel, source in FLEET.items():
            path = os.path.join(self.home, ".claude", rel)
            self.assertEqual(os.readlink(path), os.path.join(os.path.realpath(self.repo), source))
            self.assertTrue(os.path.isfile(path), rel)
        self.assertTrue(os.path.isdir(os.path.join(self.skills, "ours")))
        self.assertTrue(os.path.isdir(os.path.join(self.skills, "tdd")))

    def test_running_from_inside_the_fleet_link_changes_nothing(self):
        r = run_wire(os.path.join(self.repo, "wire.sh"), self.home, FLAG)
        self.assertEqual(r.returncode, 0, r.stderr)
        before = snapshot(self.home)
        for _ in range(2):
            r = subprocess.run(
                ["bash", "-c", 'cd "$HOME/.shyrosa" && ./wire.sh'],
                env=dict(os.environ, HOME=self.home), capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(snapshot(self.home), before)

    def test_a_matt_skill_is_linked_from_upstream(self):
        self.wire()
        self.assertEqual(self.target("tdd"), os.path.join(self.repo, "upstream", "tdd"))

    def test_an_overlay_wins_over_a_matt_skill_of_the_same_name(self):
        self.wire()
        self.assertEqual(self.target("shared"), os.path.join(self.repo, "overlay", "shared"))
        self.assertEqual(self.target("ours"), os.path.join(self.repo, "overlay", "ours"))

    def test_implement_spec_is_vendored_but_not_linked(self):
        self.wire()
        self.assertFalse(self.exists("implement-spec"))

    def test_a_link_into_a_matt_clone_is_replaced_by_one_into_upstream(self):
        self.link("tdd", "/Users/x/swMac1/matt-skills/skills/engineering/tdd")
        self.wire()
        self.assertEqual(self.target("tdd"), os.path.join(self.repo, "upstream", "tdd"))

    def test_a_stale_link_into_either_machines_clone_is_removed_and_counted(self):
        self.link("resolving-merge-conflicts",
                  "/Users/x/swMac1/matt-skills/skills/engineering/resolving-merge-conflicts")
        self.link("batch-grill-me",
                  "/home/x/swvu1/mattpocock-skills/skills/in-progress/batch-grill-me")
        last = self.wire().splitlines()[-1]
        self.assertFalse(self.exists("resolving-merge-conflicts"))
        self.assertFalse(self.exists("batch-grill-me"))
        self.assertIn("2 stale clone links removed", last)

    def test_a_link_pointing_anywhere_else_is_left_alone(self):
        elsewhere = {
            "playwright-cli": "/opt/homebrew/lib/node_modules/@playwright/cli/skill",
            "qa": "../../.agents/skills/qa",
            "gone-overlay": "/Users/x/swMac1/shyrosa/overlay/gone-overlay",
        }
        for name, target in elsewhere.items():
            self.link(name, target)
        last = self.wire().splitlines()[-1]
        for name, target in elsewhere.items():
            self.assertEqual(self.target(name), target, name)
        self.assertIn("0 stale clone links removed", last)

    def folder_targets(self):
        return {
            os.path.join(self.home, ".shyrosa"): self.repo,
            os.path.join(self.skills, "ours"): os.path.join(self.repo, "overlay", "ours"),
            os.path.join(self.skills, "tdd"): os.path.join(self.repo, "upstream", "tdd"),
        }

    def put_folder(self, target, content):
        os.makedirs(os.path.join(target, "nested", "empty"))
        with open(os.path.join(target, "nested", "SKILL.md"), "wb") as f:
            f.write(content)
        os.symlink("missing", os.path.join(target, "local-link"))

    def test_real_folders_are_moved_aside_with_contents_intact_and_linked(self):
        before = {}
        for target in self.folder_targets():
            self.put_folder(target, b"mine\x00\xff\n")
            before[target] = snapshot(target)
        r = self.run_wire()
        for target, source in self.folder_targets().items():
            self.assertEqual(os.readlink(target), source)
            self.assertEqual(snapshot(target + ASIDE), before[target])
            self.assertTrue(os.path.isdir(os.path.join(target + ASIDE, "nested", "empty")))
        self.assertEqual(r.stderr, "")
        self.assertIn("3 skills wired, 0 skipped", r.stdout.splitlines()[-1])

    def assert_taken_aside_is_skipped(self, kind):
        for target in self.folder_targets():
            self.put_folder(target, b"current\n")
            aside = target + ASIDE
            if kind == "folder":
                self.put_folder(aside, b"older\n")
            elif kind == "file":
                with open(aside, "w") as f:
                    f.write("older\n")
            else:
                os.symlink("missing", aside)
        before = snapshot(self.home)
        r = self.run_wire()
        for target in self.folder_targets():
            self.assertFalse(os.path.islink(target))
            self.assertIn(target + ASIDE + " is taken", r.stderr)
        after = snapshot(self.home)
        for path, entry in before.items():
            self.assertEqual(after[path], entry, path)
        self.assertIn("1 skills wired, 2 skipped", r.stdout.splitlines()[-1])

    def test_taken_aside_folders_are_skipped_without_changing_either_folder(self):
        self.assert_taken_aside_is_skipped("folder")

    def test_taken_aside_files_are_skipped_without_changing_either_path(self):
        self.assert_taken_aside_is_skipped("file")

    def test_dangling_aside_links_are_skipped_without_changing_either_path(self):
        self.assert_taken_aside_is_skipped("link")

    def test_occupied_clone_backup_links_survive_skip_and_stale_cleanup(self):
        for name, clone in (("ours", "matt-skills"), ("tdd", "mattpocock-skills")):
            target = os.path.join(self.skills, name)
            self.put_folder(target, b"current\x00\xff\n")
            self.link(name + ASIDE, f"/missing/{clone}/skills/{name}")
        self.link("retired", "/missing/matt-skills/skills/retired")
        before = snapshot(self.home)
        for attempt in range(2):
            r = self.run_wire()
            after = snapshot(self.home)
            for name in ("ours", "tdd"):
                with self.subTest(name=name, attempt=attempt + 1):
                    target = os.path.join(self.skills, name)
                    self.assertIn(target + ASIDE + " is taken", r.stderr)
                    self.assertFalse(os.path.islink(target))
                    for path, entry in before.items():
                        if path.startswith(f".claude/skills/{name}/") or path == f".claude/skills/{name}{ASIDE}":
                            self.assertIn(path, after)
                            self.assertEqual(after[path], entry, path)
            self.assertFalse(self.exists("retired"))
            self.assertIn("1 skills wired, 2 skipped", r.stdout.splitlines()[-1])
            removed = 1 if attempt == 0 else 0
            self.assertIn(f"{removed} stale clone links removed", r.stdout.splitlines()[-1])

    def test_a_clean_run_keeps_its_output_and_exit_status(self):
        r = self.run_wire()
        self.assertEqual(r.stderr, "")
        self.assertEqual(r.stdout, (
            f"link  ~/.shyrosa -> {self.repo}\n"
            f"link  ours -> {self.repo}/overlay/ours\n"
            f"link  shared -> {self.repo}/overlay/shared\n"
            f"link  tdd -> {self.repo}/upstream/tdd\n"
            f"link  statusline-context.py -> {self.repo}/fleet/statusline-context.py\n"
            f"link  output-styles/unslop.md -> {self.repo}/fleet/unslop.md\n"
            f"link  ~/.codex/AGENTS.md -> {self.repo}/fleet/codex/AGENTS.md\n"
            f"link  ~/.codex/skills/ours -> {self.repo}/overlay/ours\n"
            f"link  ~/.codex/skills/shared -> {self.repo}/overlay/shared\n"
            f"link  ~/.codex/skills/tdd -> {self.repo}/upstream/tdd\n"
            f"done: 3 skills wired, 0 skipped, 0 stale clone links removed, into {self.skills}; "
            "2 fleet files linked, 0 skipped; 4 codex links, 0 skipped, 0 stale codex links removed; "
            "settings.json not linked, first link needs --link-settings\n"
        ))

    def test_a_second_run_changes_nothing(self):
        self.link("tdd", "/Users/x/swMac1/matt-skills/skills/engineering/tdd")
        self.link("retired", "/Users/x/swMac1/matt-skills/skills/misc/retired")
        self.link("playwright-cli", "/opt/elsewhere/skill")
        self.wire()
        first = snapshot(self.home)
        last = self.wire().splitlines()[-1]
        self.assertEqual(snapshot(self.home), first)
        self.assertIn("0 stale clone links removed", last)

    def test_a_clone_link_to_a_skill_not_linked_is_removed(self):
        self.link("implement-spec",
                  "/Users/x/swMac1/matt-skills/skills/engineering/implement-spec")
        last = self.wire().splitlines()[-1]
        self.assertFalse(self.exists("implement-spec"))
        self.assertIn("1 stale clone links removed", last)

    def test_an_empty_upstream_links_nothing_from_it(self):
        shutil.rmtree(os.path.join(self.repo, "upstream"))
        os.makedirs(os.path.join(self.repo, "upstream"))
        self.wire()
        self.assertEqual(sorted(os.listdir(self.skills)), sorted(self.OVERLAYS))


# An ln that copies instead of linking when the target's name is $FAKE_COPY, as
# ln -s does on Windows outside Developer Mode, and runs the real ln otherwise.
FAKE_LN = """#!/bin/sh
for last; do :; done  # leaves $last set to the last argument, the target
if [ "$(basename "$last")" = "$FAKE_COPY" ] || [ "$last" = "$FAKE_COPY" ]; then
  for arg; do case "$arg" in -*) shift ;; *) break ;; esac; done  # drop the flags
  rm -rf "$2"
  exec cp -R "$1" "$2"
fi
exec %s "$@"
"""


class CopiedLink(ScratchRepo):
    """wire.sh run with an ln faked to copy (shyrosa#113)."""

    def wire_copying(self, name):
        bin_dir = os.path.join(self._tmp.name, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        fake = os.path.join(bin_dir, "ln")
        with open(fake, "w") as f:
            f.write(FAKE_LN % shutil.which("ln"))
        os.chmod(fake, 0o755)
        return run_wire(os.path.join(self.repo, "wire.sh"), self.home, FAKE_COPY=name,
                        PATH=bin_dir + os.pathsep + os.environ["PATH"])

    def assert_stops_naming_path(self, name, path):
        for attempt in range(2):
            with self.subTest(attempt=attempt + 1):
                r = self.wire_copying(name)
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertIn(path, r.stderr)
                self.assertNotIn("done:", r.stdout)
        self.assertFalse(os.path.islink(path))
        self.assertFalse(os.path.islink(path + ASIDE))
        self.assertTrue(os.path.exists(path + ASIDE))

    def test_a_copied_home_link_stops_the_run(self):
        self.assert_stops_naming_path(".shyrosa", os.path.join(self.home, ".shyrosa"))

    def test_recovery_from_the_copied_home_checkout_keeps_links_usable(self):
        r = self.wire_copying(".shyrosa")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        source = os.path.join(self.home, ".shyrosa")
        self.assertTrue(os.path.isfile(os.path.join(source, "wire.sh")))
        self.assert_home_checkout_stays_usable(source)

    def test_a_copied_skill_link_stops_the_run(self):
        self.assert_stops_naming_path("tdd", os.path.join(self.skills, "tdd"))

    def test_a_copied_fleet_link_stops_the_run(self):
        self.assert_stops_naming_path("unslop.md",
                               os.path.join(self.home, ".claude", "output-styles", "unslop.md"))

    def test_a_copied_codex_agents_link_stops_again_on_retry(self):
        self.assert_stops_naming_path("AGENTS.md", os.path.join(self.home, ".codex", "AGENTS.md"))

    def test_a_copied_codex_skill_link_stops_again_on_retry(self):
        path = os.path.join(self.home, ".codex", "skills", "tdd")
        self.assert_stops_naming_path(path, path)

    def test_the_fake_links_everything_else(self):
        r = self.wire_copying("no-such-name")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.target("tdd"), os.path.join(self.repo, "upstream", "tdd"))


class RealRepo(unittest.TestCase):
    """The real overlay/ and upstream/ wire up as the rules say."""

    def test_every_vendored_skill_loads_from_overlay_or_upstream(self):
        with tempfile.TemporaryDirectory() as home:
            r = run_wire(WIRE, home)
            self.assertEqual(r.returncode, 0, r.stderr)
            skills = os.path.join(home, ".claude", "skills")
            codex_skills = os.path.join(home, ".codex", "skills")
            overlays = skill_dirs(os.path.join(REPO, "overlay"))
            for name in skill_dirs(os.path.join(REPO, "upstream")):
                path = os.path.join(skills, name)
                if name == "implement-spec":
                    self.assertFalse(os.path.lexists(path))
                    self.assertFalse(os.path.lexists(os.path.join(codex_skills, name)))
                    continue
                top = "overlay" if name in overlays else "upstream"
                self.assertEqual(os.readlink(path), os.path.join(REPO, top, name), name)
            self.assertEqual(sorted(os.listdir(codex_skills)), sorted(os.listdir(skills)))
            for name in os.listdir(skills):
                self.assertTrue(os.path.samefile(os.path.join(codex_skills, name),
                                                os.path.join(skills, name)), name)
            self.assertTrue(os.path.samefile(os.path.join(home, ".codex", "AGENTS.md"),
                                            os.path.join(REPO, "fleet", "codex", "AGENTS.md")))


class Docs(unittest.TestCase):
    """The docs that tell agents to run wire.sh say how the settings link is first made."""

    def test_each_doc_that_runs_wire_names_the_settings_flag(self):
        for rel in ("README.md", "docs/USING.md"):
            with open(os.path.join(REPO, rel)) as f:
                self.assertIn(FLAG, f.read(), rel)


if __name__ == "__main__":
    unittest.main()
