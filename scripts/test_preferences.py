#!/usr/bin/env python3
"""Drive the preferences command in a scratch shyrosa, HOME and PATH (#136).

The process boundary and fake uname are the seams confirmed in spec #135.
Run: python3 -m unittest discover -s scripts -p test_preferences.py
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parent.parent


class Preferences(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.repo = self.scratch / "shyrosa"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(REPO / "scripts/preferences.py", self.repo / "scripts/preferences.py")
        self.home = self.scratch / "home"
        self.home.mkdir()
        self.bin = self.scratch / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin))
        self.uname("Darwin")
        for tool in ("conda", "pip", "uv", "pixi"):
            self.program(tool, "exit 0\n")

    def program(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def uname(self, kind):
        self.program("uname", f"printf '%s\\n' '{kind}'\n")

    def put(self, name, values):
        path = self.repo / "fleet/preferences" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(values), encoding="utf-8")

    def run_preferences(self):
        return subprocess.run(
            [sys.executable, str(self.repo / "scripts/preferences.py"), "--print"],
            cwd=self.home, env=self.env, capture_output=True, text=True, timeout=10,
        )

    def effective(self):
        result = self.run_preferences()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def test_user_values_are_printed_from_the_scratch_repo(self):
        self.put("user.json", {"claude": {
            "python_install": "conda-forge", "environment_manager": "conda",
            "python": "python3",
        }})
        self.assertEqual(self.effective(), {"claude": {
            "python_install": "conda-forge", "environment_manager": "conda",
            "python": "python3",
        }})

    def test_detected_machine_overrides_one_key_and_keeps_the_others(self):
        self.put("user.json", {"claude": {
            "python_install": "conda-forge", "environment_manager": "conda",
            "python": "python3",
        }})
        self.put("machines/darwin.json", {"claude": {"python_install": "uv"}})
        self.assertEqual(self.effective(), {"claude": {
            "python_install": "uv", "environment_manager": "conda",
            "python": "python3",
        }})

    def test_running_os_selects_its_file_and_ignores_the_other_kind(self):
        self.put("user.json", {"claude": {"python_install": "conda-forge", "python": "python3"}})
        self.put("machines/linux.json", {"claude": {"python_install": "pixi"}})
        self.assertEqual(self.effective(), {"claude": {
            "python_install": "conda-forge", "python": "python3",
        }})
        self.uname("Linux")
        self.assertEqual(self.effective(), {"claude": {
            "python_install": "pixi", "python": "python3",
        }})
        self.put("machines/darwin.json", {"claude": {"python_install": "uv"}})
        self.uname("Darwin")
        self.assertEqual(self.effective(), {"claude": {
            "python_install": "uv", "python": "python3",
        }})

    def test_no_files_reports_no_preferences_and_succeeds(self):
        result = self.run_preferences()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no preferences are set", result.stdout.lower())
        self.assertEqual(result.stderr, "")

    def test_python_install_accepts_only_the_four_working_combinations(self):
        for choice in ("conda-forge", "uv", "pip-venv", "pixi"):
            with self.subTest(choice=choice):
                self.put("user.json", {"claude": {"python_install": choice}})
                self.assertEqual(self.effective(), {"claude": {"python_install": choice}})
        for invalid in ("pip", "conda", "conda-defaults", "uv-conda-forge", "", None, 1, [], {}):
            with self.subTest(invalid=invalid):
                self.put("user.json", {"claude": {"python_install": invalid}})
                result = self.run_preferences()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                for name in ("conda-forge", "uv", "pip-venv", "pixi"):
                    self.assertIn(name, result.stderr)

    def test_bad_files_report_the_path_without_printing_their_values(self):
        for name in ("user.json", "machines/darwin.json"):
            for invalid in (
                [], {"claude": []}, {"claude": {"python": 3}},
                {"claude": {"environment_manager": " "}}, {"claude": {"python": None}},
                {"claude": {"api_key": "synthetic-secret-value"}},
            ):
                with self.subTest(name=name, invalid=invalid):
                    self.put(name, invalid)
                    result = self.run_preferences()
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertIn(name, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertNotIn("synthetic-secret-value", result.stderr)
            (self.repo / "fleet/preferences" / name).unlink()

    def test_machine_file_can_be_used_without_a_user_file(self):
        self.put("machines/darwin.json", {"claude": {"python_install": "uv"}})
        self.assertEqual(self.effective(), {"claude": {"python_install": "uv"}})

    def test_other_harness_sections_are_not_active(self):
        self.put("user.json", {"codex": {"python_install": "pixi"}})
        result = self.run_preferences()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no preferences are set", result.stdout.lower())
        self.put("user.json", {"claude": {"python": "python3"}, "codex": {"python": "future"}})
        self.put("machines/darwin.json", {"codex": {"python": "another"}})
        self.assertEqual(self.effective(), {"claude": {"python": "python3"}})

    def test_invalid_json_reports_which_file_needs_repair(self):
        self.put("user.json", {})
        (self.repo / "fleet/preferences/user.json").write_text("{broken", encoding="utf-8")
        result = self.run_preferences()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("user.json", result.stderr)
        self.assertIn("invalid JSON", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_utf8_reports_the_file_without_echoing_its_contents(self):
        self.put("user.json", {})
        (self.repo / "fleet/preferences/user.json").write_bytes(b'\xffsynthetic-secret-value')
        result = self.run_preferences()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("user.json", result.stderr)
        self.assertIn("UTF-8", result.stderr)
        self.assertNotIn("synthetic-secret-value", result.stderr)

    def test_invalid_machine_choice_is_rejected_even_with_a_valid_user_choice(self):
        self.put("user.json", {"claude": {"python_install": "uv"}})
        self.put("machines/darwin.json", {"claude": {"python_install": "pip"}})
        result = self.run_preferences()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("machines/darwin.json", result.stderr)
        for name in ("conda-forge", "uv", "pip-venv", "pixi"):
            self.assertIn(name, result.stderr)

    def test_model_is_rejected_in_user_and_machine_files_and_settings_stay_unchanged(self):
        settings = self.repo / "fleet/settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text('{"model": "opus"}\n', encoding="utf-8")
        before = settings.read_bytes()
        for name in ("user.json", "machines/darwin.json"):
            with self.subTest(name=name):
                self.put(name, {"claude": {"model": "another-model"}})
                result = self.run_preferences()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn(name, result.stderr)
                self.assertIn("supported claude keys", result.stderr)
                self.assertEqual(settings.read_bytes(), before)
                (self.repo / "fleet/preferences" / name).unlink()

    def test_printing_changes_no_files_and_does_not_read_preferences_from_home(self):
        self.put("user.json", {"claude": {"python_install": "uv", "python": "python3"}})
        settings = self.repo / "fleet/settings.json"
        settings.write_text('{"model": "different"}\n', encoding="utf-8")
        (self.home / "user.json").write_text('{"claude": {"python": "home"}}', encoding="utf-8")
        before = {p.relative_to(self.scratch): p.read_bytes()
                  for p in self.scratch.rglob("*") if p.is_file()}
        self.assertEqual(self.effective(), {"claude": {"python_install": "uv", "python": "python3"}})
        after = {p.relative_to(self.scratch): p.read_bytes()
                 for p in self.scratch.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_uname_failure_or_unsafe_output_is_an_error(self):
        for kind in ("", "../user", "Darwin/../../user"):
            with self.subTest(kind=kind):
                self.uname(kind)
                result = self.run_preferences()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("uname", result.stderr)
        self.program("uname", "exit 1\n")
        result = self.run_preferences()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("uname", result.stderr)

    def test_manager_file_records_only_the_confirmed_conda_forge_choice(self):
        source = REPO / "fleet/preferences/user.json"
        self.assertEqual(json.loads(source.read_text(encoding="utf-8")), {
            "claude": {"python_install": "conda-forge"},
        })
        target = self.repo / "fleet/preferences/user.json"
        target.parent.mkdir(parents=True)
        shutil.copy2(source, target)
        self.assertEqual(self.effective(), {"claude": {"python_install": "conda-forge"}})


if __name__ == "__main__":
    unittest.main()
