#!/usr/bin/env python3
"""Exercise model drift through spec #135's confirmed briefing process seam (#139)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parent.parent
GIT = shutil.which("git")
NOTICE = ('Claude model: fleet/settings.json says "opus[1m]" but git has "opus". '
          'Ask the person whether to keep the change or put "opus" back; '
          'do not change it yourself.')


class ModelDrift(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="shyrosa-139-")
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.repo = self.scratch / "shyrosa"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(REPO / "scripts/preferences.py", self.repo / "scripts/preferences.py")
        self.settings = self.repo / "fleet/settings.json"
        self.settings.parent.mkdir()
        self.home = self.scratch / "home"
        self.home.mkdir()
        self.bin = self.scratch / "bin"
        self.bin.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("GIT_") and key not in ("CONDA_EXE", "MAMBA_EXE")}
        self.env.update(HOME=str(self.home), PATH=str(self.bin), PYTHONDONTWRITEBYTECODE="1",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_COUNT="0", GIT_TERMINAL_PROMPT="0")
        uname = self.bin / "uname"
        uname.write_text("#!/bin/sh\nprintf 'Darwin\\n'\n", encoding="utf-8")
        uname.chmod(0o755)
        (self.bin / "git").symlink_to(GIT)

    def git(self, *args):
        return subprocess.run(
            [GIT, *args], cwd=self.repo, env=self.env, capture_output=True,
            text=True, check=True, timeout=10,
        ).stdout

    def init_git(self):
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")

    def committed_settings(self, document):
        self.settings.write_text(json.dumps(document) + "\n", encoding="utf-8")
        self.init_git()
        self.git("add", "fleet/settings.json")
        self.git("commit", "-qm", "Synthetic committed settings")

    def run_mode(self, mode="--brief"):
        return subprocess.run(
            [sys.executable, str(self.repo / "scripts/preferences.py"), mode],
            input='{"hook_event_name":"SessionStart","source":"startup"}',
            cwd=self.home, env=self.env, capture_output=True, text=True, timeout=10,
        )

    def brief(self):
        before = {p.relative_to(self.scratch): p.read_bytes()
                  for p in self.scratch.rglob("*") if p.is_file()}
        result = self.run_mode()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        after = {p.relative_to(self.scratch): p.read_bytes()
                 for p in self.scratch.rglob("*") if p.is_file()}
        self.assertEqual(after, before)
        return result.stdout

    def test_drift_names_both_models_once_after_preferences_without_changing_files(self):
        self.committed_settings({"model": "opus", "unrelated": True})
        self.settings.write_bytes(b'{\n  "model": "opus[1m]", "unrelated": true\n}\n')
        preferences = self.repo / "fleet/preferences/user.json"
        preferences.parent.mkdir()
        preferences.write_text('{"claude":{"python":"/bin/sh"}}\n', encoding="utf-8")
        self.assertEqual(self.brief(), "Python interpreter: /bin/sh.\n" + NOTICE + "\n")

    def test_drift_is_reported_even_without_tool_preferences(self):
        self.committed_settings({"model": "opus"})
        self.settings.write_text('{"model":"opus[1m]"}\n', encoding="utf-8")
        self.assertEqual(self.brief(), "No preferences are set.\n" + NOTICE + "\n")

    def test_agreement_and_unrelated_settings_changes_do_not_report_drift(self):
        self.committed_settings({"model": "opus", "unrelated": True})
        self.settings.write_text('{"unrelated":false,"model":"opus"}\n', encoding="utf-8")
        self.assertEqual(self.brief(), "No preferences are set.\n")

    def test_staged_model_is_compared_with_head_and_keeps_json_quotes_on_one_line(self):
        self.committed_settings({"model": "sonnet"})
        self.settings.write_text(json.dumps({"model": 'custom"model\nnext'}) + "\n",
                                 encoding="utf-8")
        self.git("add", "fleet/settings.json")
        self.assertEqual(self.brief(), 'No preferences are set.\n'
                         'Claude model: fleet/settings.json says "custom\\"model\\nnext" '
                         'but git has "sonnet". Ask the person whether to keep the change '
                         'or put "sonnet" back; do not change it yourself.\n')

    def test_print_and_default_mode_do_not_report_drift(self):
        self.committed_settings({"model": "opus"})
        self.settings.write_text('{"model":"opus[1m]"}\n', encoding="utf-8")
        for args in (("--print",), ()):
            with self.subTest(args=args):
                result = subprocess.run(
                    [sys.executable, str(self.repo / "scripts/preferences.py"), *args],
                    cwd=self.home, env=self.env, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(result.stdout, "No preferences are set.\n")

    def test_outside_git_or_without_a_committed_settings_file_still_briefs(self):
        self.settings.write_text('{"model":"opus[1m]"}\n', encoding="utf-8")
        self.assertEqual(self.brief(), "No preferences are set.\n")
        self.init_git()
        self.assertEqual(self.brief(), "No preferences are set.\n")
        self.git("commit", "--allow-empty", "-qm", "No tracked settings")
        self.assertEqual(self.brief(), "No preferences are set.\n")

    def test_deleted_model_reports_the_committed_value_without_changing_files(self):
        self.committed_settings({"model": "opus"})
        self.settings.write_text('{"unrelated":true}\n', encoding="utf-8")
        self.assertEqual(self.brief(), 'No preferences are set.\n'
                         'Claude model: fleet/settings.json has no model line but git has "opus". '
                         'Ask the person whether to keep the change or put "opus" back; '
                         'do not change it yourself.\n')

    def test_neither_copy_has_a_model_does_not_report_drift(self):
        self.committed_settings({"unrelated": True})
        self.settings.write_text('{"unrelated":false}\n', encoding="utf-8")
        self.assertEqual(self.brief(), "No preferences are set.\n")

    def test_added_model_without_a_committed_model_does_not_report_drift(self):
        self.committed_settings({"unrelated": True})
        self.settings.write_text('{"model":"opus[1m]"}\n', encoding="utf-8")
        self.assertEqual(self.brief(), "No preferences are set.\n")

    def test_unavailable_git_does_not_interrupt_preferences(self):
        self.committed_settings({"model": "opus"})
        self.settings.write_text('{"model":"opus[1m]"}\n', encoding="utf-8")
        (self.bin / "git").unlink()
        self.assertEqual(self.brief(), "No preferences are set.\n")

    def test_stalled_git_leaves_preferences_intact_and_returns_within_about_two_seconds(self):
        self.committed_settings({"model": "opus"})
        self.settings.write_text('{"model":"opus[1m]"}\n', encoding="utf-8")
        preferences = self.repo / "fleet/preferences/user.json"
        preferences.parent.mkdir()
        preferences.write_text('{"claude":{"python":"/bin/sh"}}\n', encoding="utf-8")
        git = self.bin / "git"
        git.unlink()
        git.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(6)\n", encoding="utf-8")
        git.chmod(0o755)
        started = time.monotonic()
        self.assertEqual(self.brief(), "Python interpreter: /bin/sh.\n")
        self.assertLess(time.monotonic() - started, 3)

    def test_missing_or_unreadable_settings_data_does_not_interrupt_briefing(self):
        self.committed_settings({"model": "opus"})
        for data in (b'{broken', b'\xff', b'[]', b'{"model":null}', b'{"model":42}'):
            with self.subTest(data=data):
                self.settings.write_bytes(data)
                self.assertEqual(self.brief(), "No preferences are set.\n")
        self.settings.unlink()
        self.assertEqual(self.brief(), "No preferences are set.\n")

    def test_git_worktree_uses_its_own_saved_settings(self):
        self.committed_settings({"model": "opus"})
        worktree = self.scratch / "worktree"
        self.git("add", "scripts/preferences.py")
        self.git("commit", "-qm", "Synthetic briefing script")
        self.git("worktree", "add", "-qb", "worker", str(worktree))
        self.repo = worktree
        self.settings = worktree / "fleet/settings.json"
        self.settings.write_text('{"model":"opus[1m]"}\n', encoding="utf-8")
        self.assertEqual(self.brief(), "No preferences are set.\n" + NOTICE + "\n")


if __name__ == "__main__":
    unittest.main()
