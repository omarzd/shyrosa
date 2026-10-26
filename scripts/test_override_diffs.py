#!/usr/bin/env python3
"""Tests for scripts/override-diffs.py, the recorded override diffs (shyrosa#107).

Two tests read this repo itself, as test_export_public.py reads the real rulebook:
each recorded diff in docs/overrides/ equals what diff gives today between upstream/
and the matching overlay, and no file agents follow today names the old glossary
file. The rest drive the command over a scratch repo in a temporary folder.

This file names the old glossary files on purpose.
"""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SCRIPT = os.path.join(_HERE, "override-diffs.py")
_spec = importlib.util.spec_from_file_location("override_diffs", _SCRIPT)
od = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(od)

# The files agents follow today. Records and the rename script are outside the check.
FOLLOWED = ["WORKFLOW-RULEBOOK.md", "WORKFLOW-VOCAB.md", "CLAUDE.md", "docs/agents",
            "overlay", "fleet", ".claude/output-styles"]
# An old file name, or a section of the old glossary written `CONTEXT §5`.
OLD_NAME = re.compile(r"(?<![\w-])CONTEXT((-MAP|-FORMAT)?\.md(?!\w)| §)")


def old_name_hits(root):
    """`path:line` for each line under FOLLOWED in `root` that names the old glossary."""
    found = []
    for entry in FOLLOWED:
        top = os.path.join(root, entry)
        paths = [top] if os.path.isfile(top) else [
            os.path.join(d, f) for d, _, fs in os.walk(top) for f in fs]
        for path in paths:
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except UnicodeDecodeError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if OLD_NAME.search(line):
                    found.append(f"{os.path.relpath(path, root)}:{n}")
    return found


class ThisRepo(unittest.TestCase):

    def test_every_overlay_with_a_matt_base_has_a_record(self):
        for name in od.overridden(_ROOT):
            with self.subTest(name):
                self.assertTrue(os.path.exists(od.record_path(_ROOT, name)))

    def test_each_recorded_diff_matches_the_overlay_today(self):
        for name in od.overridden(_ROOT):
            with self.subTest(name):
                self.assertEqual(od.recorded(_ROOT, name), od.current(_ROOT, name),
                                 f"run scripts/override-diffs.py to regenerate {name}.diff")

    def test_no_file_agents_follow_names_the_old_glossary(self):
        self.assertEqual(old_name_hits(_ROOT), [])

    def test_ask_matt_defers_smart_zone_bounds_to_the_rulebook(self):
        with open(os.path.join(_ROOT, "overlay", "ask-matt", "SKILL.md"),
                  encoding="utf-8") as f:
            paragraphs = f.read().split("\n\n")
        smart_zone = next(p for p in paragraphs if "[smart zone]" in p)
        self.assertIn("~/.shyrosa/WORKFLOW-RULEBOOK.md", smart_zone)
        self.assertIn("Relief and context", smart_zone)
        self.assertNotRegex(smart_zone, r"\d",
                            "smart-zone bounds belong only in the rulebook")

    def test_fix_round_resume_repeats_the_launch_settings(self):
        with open(os.path.join(_ROOT, "overlay", "tmux-orchestrator", "SKILL.md"),
                  encoding="utf-8") as f:
            recycling = f.read().split("## Recycling a worker pane\n", 1)[1]
        recycling = recycling.split("\n## ", 1)[0]
        commands = re.findall(r"`(claude --resume [^`]+)`", recycling)
        self.assertTrue(commands, "fix-round guidance must show a resume command")
        for command in commands:
            for flag in ("--model", "--effort", "--permission-mode"):
                with self.subTest(command=command, flag=flag):
                    self.assertIn(flag + " <copied>", command)

class OldNameCheck(unittest.TestCase):
    """The old-name check over a scratch tree, so a gap in it shows up red."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def plant(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return [f"{rel}:1"]

    def test_it_finds_each_old_file_name(self):
        hits = self.plant("CLAUDE.md", "read CONTEXT.md\n")
        hits += self.plant("docs/agents/domain.md", "or CONTEXT-MAP.md\n")
        hits += self.plant("overlay/a/FORMAT.md", "see CONTEXT-FORMAT.md\n")
        self.assertEqual(sorted(old_name_hits(self.root)), sorted(hits))

    def test_it_finds_the_section_form(self):
        hits = self.plant("overlay/grill-spec/SKILL.md", "<domain-sha> (CONTEXT \u00a7N)\n")
        self.assertEqual(old_name_hits(self.root), hits)

    def test_it_reads_the_projects_output_styles(self):
        hits = self.plant(".claude/output-styles/unslop.md", "`CONTEXT.md` for the domain\n")
        self.assertEqual(old_name_hits(self.root), hits)

    def test_it_leaves_other_names_alone(self):
        self.plant("CLAUDE.md", "BOUNDED-CONTEXT.md, CONTEXT.mdx, GLOSSARY.md, the context\n")
        self.assertEqual(old_name_hits(self.root), [])


class Command(unittest.TestCase):
    """A scratch repo with one overridden skill and one overlay of our own."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.write("upstream/skill-a/SKILL.md", "one\ntwo\n")
        self.write("upstream/skill-a/agents/x.yaml", "x\n")
        self.write("overlay/skill-a/SKILL.md", "one\ntwo, ours\n")
        self.write("overlay/skill-a/EXTRA.md", "ours\n")
        self.write("overlay/ours-only/SKILL.md", "ours\n")
        os.makedirs(os.path.join(self.root, "docs", "overrides"))

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel)) as f:
            return f.read()

    def run_it(self, *args, env=None):
        return subprocess.run([sys.executable, _SCRIPT, *args, self.root],
                              capture_output=True, text=True, env=env)

    def test_it_writes_a_record_only_for_an_overlay_with_a_matt_base(self):
        self.assertEqual(self.run_it().returncode, 0)
        self.assertEqual(os.listdir(os.path.join(self.root, "docs", "overrides")),
                         ["skill-a.diff"])

    def test_the_record_is_diff_ru_from_the_root_without_timestamps(self):
        self.run_it()
        self.assertEqual(self.read("docs/overrides/skill-a.diff"), (
            "Only in overlay/skill-a: EXTRA.md\n"
            "diff -ru upstream/skill-a/SKILL.md overlay/skill-a/SKILL.md\n"
            "--- upstream/skill-a/SKILL.md\n"
            "+++ overlay/skill-a/SKILL.md\n"
            "@@ -1,2 +1,2 @@\n"
            " one\n"
            "-two\n"
            "+two, ours\n"
            "Only in upstream/skill-a: agents\n"))

    def test_the_record_does_not_depend_on_the_diff_on_path(self):
        # The box's GNU diff and the Mac's Apple diff lay hunks out differently.
        self.run_it()
        expected = self.read("docs/overrides/skill-a.diff")
        os.remove(os.path.join(self.root, "docs/overrides/skill-a.diff"))
        fake = os.path.join(self.root, "fakebin")
        self.write("fakebin/diff", "#!/bin/sh\necho '@@ -5,8 +5,13 @@ another layout'\nexit 1\n")
        os.chmod(os.path.join(fake, "diff"), 0o755)
        env = dict(os.environ, PATH=fake + os.pathsep + os.environ["PATH"])
        self.assertEqual(self.run_it(env=env).returncode, 0)
        self.assertEqual(self.read("docs/overrides/skill-a.diff"), expected)

    def test_a_shared_subfolder_is_walked_in_name_order(self):
        self.write("overlay/skill-a/agents/x.yaml", "y\n")
        self.run_it()
        record = self.read("docs/overrides/skill-a.diff")
        self.assertTrue(record.endswith(
            "diff -ru upstream/skill-a/agents/x.yaml overlay/skill-a/agents/x.yaml\n"
            "--- upstream/skill-a/agents/x.yaml\n"
            "+++ overlay/skill-a/agents/x.yaml\n"
            "@@ -1 +1 @@\n"
            "-x\n"
            "+y\n"), record)

    def test_a_missing_final_newline_is_marked_as_diff_marks_it(self):
        self.write("overlay/skill-a/SKILL.md", "one\ntwo, ours")
        self.run_it()
        self.assertIn(
            "@@ -1,2 +1,2 @@\n"
            " one\n"
            "-two\n"
            "+two, ours\n"
            "\\ No newline at end of file\n",
            self.read("docs/overrides/skill-a.diff"))

    def test_a_note_at_the_top_of_a_record_survives_a_rewrite(self):
        self.write("docs/overrides/skill-a.diff", "# A note.\n# Two lines.\nstale\n")
        self.run_it()
        record = self.read("docs/overrides/skill-a.diff")
        self.assertTrue(record.startswith("# A note.\n# Two lines.\nOnly in overlay"))

    def test_check_names_a_stale_record_and_fails(self):
        self.run_it()
        self.write("overlay/skill-a/SKILL.md", "one\ntwo, ours again\n")
        result = self.run_it("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("skill-a", result.stdout)
        self.assertNotIn("ours again", self.read("docs/overrides/skill-a.diff"))

    def test_check_passes_when_every_record_is_current(self):
        self.run_it()
        self.assertEqual(self.run_it("--check").returncode, 0)

    def test_a_second_run_changes_nothing(self):
        self.run_it()
        first = self.read("docs/overrides/skill-a.diff")
        self.run_it()
        self.assertEqual(self.read("docs/overrides/skill-a.diff"), first)


if __name__ == "__main__":
    unittest.main()
