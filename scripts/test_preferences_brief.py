#!/usr/bin/env python3
"""Exercise SessionStart briefing at spec #135's confirmed process seam (#138)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parent.parent

# The director approved this filesystem boundary for process isolation (#138).
PROCESS_WRAPPER = '''\
import os
import runpy
import sys
from unittest import mock

system_bases = ("/opt/homebrew/Caskroom/miniforge/base", "/opt/miniconda3", "/opt/conda")
real_isfile, real_access = os.path.isfile, os.access

def system_path(path):
    name = os.fspath(path)
    return any(name == base or name.startswith(base + "/") for base in system_bases)

def isfile(path):
    return False if system_path(path) else real_isfile(path)

def access(path, mode, *args, **kwargs):
    return False if system_path(path) else real_access(path, mode, *args, **kwargs)

script = sys.argv.pop(1)
with mock.patch("os.path.isfile", side_effect=isfile), mock.patch("os.access", side_effect=access):
    runpy.run_path(script, run_name="__main__")
'''


class Briefing(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="shyrosa-138-")
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.wrapper = self.scratch / "briefing-wrapper.py"
        self.wrapper.write_text(PROCESS_WRAPPER, encoding="utf-8")
        self.repo = self.scratch / "shyrosa"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(REPO / "scripts/preferences.py", self.repo / "scripts/preferences.py")
        self.home = self.scratch / "home"
        self.home.mkdir()
        self.bin = self.scratch / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin),
                        PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("CONDA_EXE", None)
        self.env.pop("MAMBA_EXE", None)
        self.uname("Darwin")

    def program(self, name, body='printf invoked >> "$HOME/tool-invocations"\nexit 99\n'):
        path = self.bin / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def uname(self, kind):
        self.program("uname", f"printf '%s\\n' '{kind}'\n")

    def put(self, name, values):
        path = self.repo / "fleet/preferences" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"claude": values}), encoding="utf-8")

    def run_mode(self, mode):
        return subprocess.run(
            [sys.executable, str(self.wrapper), str(self.repo / "scripts/preferences.py"), mode],
            input=json.dumps({"hook_event_name": "SessionStart", "source": "startup",
                              "cwd": str(self.home)}),
            cwd=self.home, env=self.env, capture_output=True, text=True, timeout=10,
        )

    def brief(self):
        result = self.run_mode("--brief")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def assert_diagnostic_only(self, *details):
        before = {p.relative_to(self.scratch): p.read_bytes()
                  for p in self.scratch.rglob("*") if p.is_file() and p.stat().st_mode & 0o400}
        result = self.run_mode("--brief")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
        self.assertTrue(result.stdout.startswith("Preferences:"), result.stdout)
        for detail in details:
            self.assertIn(detail, result.stdout)
        self.assertNotIn("No preferences are set", result.stdout)
        self.assertNotIn("Python packages:", result.stdout)
        self.assertNotIn("Traceback", result.stdout)
        self.assertNotIn("synthetic-secret-value", result.stdout)
        printed = self.run_mode("--print")
        self.assertEqual(printed.returncode, 2)
        self.assertEqual(printed.stdout, "")
        for detail in details:
            self.assertIn(detail, printed.stderr)
        after = {p.relative_to(self.scratch): p.read_bytes()
                 for p in self.scratch.rglob("*") if p.is_file() and p.stat().st_mode & 0o400}
        self.assertEqual(after, before)

    def test_malformed_user_file_briefs_a_diagnostic_only_and_print_stays_strict(self):
        self.put("user.json", {})
        (self.repo / "fleet/preferences/user.json").write_text("{synthetic-secret-value")
        self.put("machines/darwin.json", {"python_install": "uv"})
        self.assert_diagnostic_only("user.json", "invalid JSON")

    def test_malformed_machine_file_briefs_a_diagnostic_only_and_print_stays_strict(self):
        self.put("user.json", {"python_install": "conda-forge"})
        self.put("machines/darwin.json", {})
        (self.repo / "fleet/preferences/machines/darwin.json").write_text("{broken")
        self.assert_diagnostic_only("machines/darwin.json", "invalid JSON")

    def test_invalid_value_briefs_a_diagnostic_only_and_print_stays_strict(self):
        self.put("user.json", {"python_install": "synthetic-secret-value"})
        self.assert_diagnostic_only("user.json", "must be one of")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0,
                     "root can read files despite mode 000")
    def test_unreadable_file_briefs_a_diagnostic_only_and_print_stays_strict(self):
        self.put("user.json", {"python_install": "conda-forge"})
        path = self.repo / "fleet/preferences/user.json"
        path.chmod(0)
        self.addCleanup(path.chmod, 0o600)
        self.assert_diagnostic_only("user.json", "Permission denied")

    def test_failing_uname_briefs_a_diagnostic_only_and_print_stays_strict(self):
        self.put("user.json", {"python_install": "conda-forge"})
        self.program("uname", "exit 1\n")
        self.assert_diagnostic_only("uname", "exit status 1")

    def test_unavailable_uname_briefs_a_diagnostic_only_and_print_stays_strict(self):
        (self.bin / "uname").unlink()
        self.assert_diagnostic_only("uname", "No such file")

    def test_no_files_is_one_line_and_succeeds(self):
        self.assertEqual(self.brief(), "No preferences are set.\n")

    def test_conda_forge_preference_with_conda_present(self):
        self.put("user.json", {"python_install": "conda-forge"})
        self.program("conda")
        output = self.brief()
        self.assertIn("conda from conda-forge", output)
        self.assertIn("conda install -c conda-forge", output)
        self.assertNotIn("not on PATH", output)
        self.assertNotIn("brew install", output)

    def test_miniforge_installed_outside_path_is_not_reported_missing(self):
        self.put("user.json", {"python_install": "conda-forge", "environment_manager": "conda"})
        self.program(self.home / "miniforge3/bin/conda")
        before = {p.relative_to(self.scratch): p.read_bytes()
                  for p in self.scratch.rglob("*") if p.is_file()}
        output = self.brief()
        self.assertIn("conda from conda-forge", output)
        self.assertIn("Environment manager: conda", output)
        self.assertNotIn("not on PATH", output)
        self.assertNotIn("To install", output)
        self.assertNotIn("brew install", output)
        after = {p.relative_to(self.scratch): p.read_bytes()
                 for p in self.scratch.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_other_home_installs_are_not_reported_missing(self):
        for choice, tool, location in (("conda-forge", "mamba", "mambaforge/condabin/mamba"),
                                       ("uv", "uv", ".cargo/bin/uv"),
                                       ("pixi", "pixi", ".pixi/bin/pixi")):
            with self.subTest(tool=tool):
                self.put("user.json", {"python_install": choice, "environment_manager": tool})
                path = self.home / location
                self.program(path)
                output = self.brief()
                self.assertIn(f"Environment manager: {tool}", output)
                self.assertNotIn("not on PATH", output)
                self.assertNotIn("To install", output)
                self.assertFalse((self.home / "tool-invocations").exists())
                path.unlink()

    def test_environment_variables_locate_tools_outside_path(self):
        for tool, variable in (("conda", "CONDA_EXE"), ("mamba", "MAMBA_EXE")):
            with self.subTest(tool=tool):
                self.put("user.json", {"python_install": "conda-forge"})
                path = self.scratch / "custom" / tool
                self.program(path)
                self.env[variable] = str(path)
                output = self.brief()
                self.assertIn("conda from conda-forge", output)
                self.assertNotIn("not on PATH", output)
                self.assertNotIn("To install", output)
                self.assertFalse((self.home / "tool-invocations").exists())
                self.env.pop(variable)
                path.unlink()

    def test_missing_conda_names_the_install_command_for_the_running_os(self):
        self.put("user.json", {"python_install": "conda-forge"})
        for kind, command in (
            ("Darwin", "brew install --cask miniforge"),
            ("Linux", "curl -L -O https://github.com/conda-forge/miniforge/releases/latest/"
             "download/Miniforge3-$(uname)-$(uname -m).sh && "
             "bash Miniforge3-$(uname)-$(uname -m).sh"),
        ):
            with self.subTest(kind=kind):
                self.uname(kind)
                output = self.brief()
                self.assertIn("conda is not on PATH", output)
                self.assertIn(command, output)
                self.program("conda")
                output = self.brief()
                self.assertNotIn("not on PATH", output)
                self.assertNotIn(command, output)
                (self.bin / "conda").unlink()

    def test_mamba_also_satisfies_the_conda_forge_choice(self):
        self.put("user.json", {"python_install": "conda-forge"})
        self.program("mamba")
        output = self.brief()
        self.assertIn("conda from conda-forge", output)
        self.assertIn("mamba install -c conda-forge", output)
        self.assertNotIn("not on PATH", output)
        self.assertNotIn("brew install", output)

    def test_other_install_choices_check_only_the_needed_tool(self):
        for choice, tool, preference, darwin, linux in (
            ("uv", "uv", "uv pip install", "brew install uv",
             "curl -LsSf https://astral.sh/uv/install.sh | sh"),
            ("pixi", "pixi", "pixi add", "brew install pixi",
             "curl -fsSL https://pixi.sh/install.sh | sh"),
            ("pip-venv", "python3", "pip with a venv", "brew install python",
             "sudo apt install python3 python3-venv"),
        ):
            for kind, command in (("Darwin", darwin), ("Linux", linux)):
                with self.subTest(choice=choice, kind=kind):
                    self.put("user.json", {"python_install": choice})
                    self.uname(kind)
                    output = self.brief()
                    self.assertIn(preference, output)
                    self.assertIn(f"{tool} is not on PATH", output)
                    self.assertIn(command, output)
                    self.program(tool)
                    output = self.brief()
                    self.assertIn(preference, output)
                    self.assertNotIn("not on PATH", output)
                    self.assertNotIn(command, output)
                    (self.bin / tool).unlink()

    def test_named_commands_are_stated_and_missing_ones_have_no_install_command(self):
        self.put("user.json", {"environment_manager": "custom-env", "python": "custom-python"})
        output = self.brief()
        self.assertIn("Environment manager: custom-env", output)
        self.assertIn("Python interpreter: custom-python", output)
        self.assertEqual([line for line in output.splitlines() if "not on PATH" in line], [
            "custom-env is not on PATH.", "custom-python is not on PATH.",
        ])
        self.assertNotIn("install", output.lower())
        for name in ("custom-env", "custom-python"):
            self.program(name)
        output = self.brief()
        self.assertIn("custom-env", output)
        self.assertIn("custom-python", output)
        self.assertNotIn("not on PATH", output)

    def test_one_notice_per_missing_tool_even_when_preferences_share_it(self):
        self.put("user.json", {"python_install": "pip-venv", "python": "python3",
                               "environment_manager": "python3"})
        self.assertEqual(self.brief().count("python3 is not on PATH"), 1)

    def test_other_os_names_the_missing_tool_without_an_install_command(self):
        self.uname("FreeBSD")
        for choice, tool in (("conda-forge", "conda"), ("uv", "uv"),
                             ("pixi", "pixi"), ("pip-venv", "python3")):
            with self.subTest(choice=choice):
                self.put("user.json", {"python_install": choice})
                self.assertEqual([line for line in self.brief().splitlines()
                                  if "not on PATH" in line], [f"{tool} is not on PATH."])

    def test_briefing_uses_the_effective_preferences_for_the_running_os(self):
        self.put("user.json", {"python_install": "conda-forge", "python": "python3"})
        self.put("machines/darwin.json", {"python_install": "uv"})
        self.put("machines/linux.json", {"environment_manager": "pixi"})
        output = self.brief()
        self.assertIn("uv pip install", output)
        self.assertIn("Python interpreter: python3", output)
        self.assertNotIn("conda", output)
        self.assertNotIn("pixi", output)
        self.uname("Linux")
        output = self.brief()
        self.assertIn("conda from conda-forge", output)
        self.assertIn("Environment manager: pixi", output)
        self.assertIn("Python interpreter: python3", output)
        self.assertNotIn("uv", output)

    def test_briefing_neither_executes_tools_nor_changes_files(self):
        self.put("user.json", {"python_install": "conda-forge", "environment_manager": "conda",
                               "python": "python3"})
        settings = self.repo / "fleet/settings.json"
        shutil.copy2(REPO / "fleet/settings.json", settings)
        for name in ("conda", "mamba", "python3", "pip", "uv", "pixi", "brew", "curl", "sh", "bash"):
            self.program(name)
        for present in (True, False):
            with self.subTest(present=present):
                if not present:
                    (self.bin / "conda").unlink()
                    (self.bin / "mamba").unlink()
                before = {p.relative_to(self.scratch): p.read_bytes()
                          for p in self.scratch.rglob("*") if p.is_file()}
                self.brief()
                after = {p.relative_to(self.scratch): p.read_bytes()
                         for p in self.scratch.rglob("*") if p.is_file()}
                self.assertEqual(after, before)

    def test_registered_hook_runs_with_a_scratch_home(self):
        self.put("user.json", {"python_install": "conda-forge"})
        self.program("conda")
        (self.bin / "python3").symlink_to(sys.executable)
        (self.home / ".shyrosa").symlink_to(self.repo, target_is_directory=True)
        settings = self.repo / "fleet/settings.json"
        shutil.copy2(REPO / "fleet/settings.json", settings)
        hooks = json.loads(settings.read_text())["hooks"]["SessionStart"]
        command = next(hook["command"] for entry in hooks for hook in entry["hooks"]
                       if "preferences.py --brief" in hook["command"])
        result = subprocess.run(
            ["/bin/sh", "-c", command], input='{"hook_event_name":"SessionStart"}',
            cwd=self.home, env=self.env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("conda from conda-forge", result.stdout)
        self.assertNotIn("not on PATH", result.stdout)


if __name__ == "__main__":
    unittest.main()
