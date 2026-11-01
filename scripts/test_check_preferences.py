#!/usr/bin/env python3
"""Drive the Bash preference guard through synthetic stdin in scratch (#140)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parent.parent
INSTALLS = {
    "pip-venv": ("pip install pandas", "pip3 install pandas",
                 "python -m pip install pandas", "python3 -m pip install pandas"),
    "uv": ("uv pip install pandas", "uv add pandas", "uv sync"),
    "conda-forge": ("conda install pandas", "mamba install pandas"),
    "pixi": ("pixi add pandas", "pixi install"),
}

# #140's director approved the same filesystem boundary as #138's process tests.
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
sys.path.insert(0, os.path.dirname(script))
with mock.patch("os.path.isfile", side_effect=isfile), mock.patch("os.access", side_effect=access):
    runpy.run_path(script, run_name="__main__")
'''


class CommandPreferences(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="140-guard-")
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.wrapper = self.scratch / "guard-wrapper.py"
        self.wrapper.write_text(PROCESS_WRAPPER, encoding="utf-8")
        self.repo = self.scratch / "shyrosa"
        (self.repo / "scripts").mkdir(parents=True)
        for name in ("preferences.py", "check-preferences.py"):
            shutil.copy2(REPO / "scripts" / name, self.repo / "scripts" / name)
        self.home = self.scratch / "home"
        self.home.mkdir()
        self.project = self.scratch / "project"
        self.project.mkdir()
        self.bin = self.scratch / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin),
                        PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("CONDA_EXE", None)
        self.env.pop("MAMBA_EXE", None)
        self.program("uname", "printf 'Darwin\\n'\n")
        for tool in ("conda", "pip", "uv", "pixi"):
            self.program(tool, "exit 99\n")  # discovery only; never execute an installer

    def program(self, name, body):
        path = self.bin / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def prefer(self, choice, name="user.json"):
        path = self.repo / "fleet/preferences" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"claude": {"python_install": choice}}), encoding="utf-8")

    def run_payload(self, payload, isolate_system=True):
        script = str(self.repo / "scripts/check-preferences.py")
        command = [sys.executable, "-B"]
        if isolate_system:
            command.append(str(self.wrapper))
        return subprocess.run(
            [*command, script],
            input=payload, cwd=self.home, env=self.env,
            capture_output=True, text=True, timeout=15,
        )

    def guard(self, command, isolate_system=True):
        return self.run_payload(json.dumps({
            "tool_name": "Bash", "tool_input": {"command": command},
            "cwd": str(self.project),
        }), isolate_system=isolate_system)

    def assertAllowed(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout + result.stderr, "")

    def test_pip_is_refused_with_the_conda_forge_replacement(self):
        self.prefer("conda-forge")
        result = self.guard("pip install pandas numpy")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "Use conda install -c conda-forge <packages> instead.\n")

    def test_miniforge_conda_off_path_refuses_installs_without_running_the_tool(self):
        self.prefer("conda-forge")
        (self.bin / "conda").unlink()
        self.assertAllowed(self.guard("pip install pandas"))
        conda = self.home / "miniforge3/bin/conda"
        self.program(conda, 'printf invoked > "$HOME/tool-invocations"\nexit 99\n')
        before = {p.relative_to(self.scratch): p.read_bytes()
                  for p in self.scratch.rglob("*") if p.is_file()}
        result = self.guard("pip install pandas")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "Use conda install -c conda-forge <packages> instead.\n")
        after = {p.relative_to(self.scratch): p.read_bytes()
                 for p in self.scratch.rglob("*") if p.is_file()}
        self.assertEqual(after, before)
        conda.unlink()
        self.assertAllowed(self.guard("pip install pandas"))

    def test_conda_exe_can_locate_a_scratch_tool_off_path(self):
        self.prefer("conda-forge")
        (self.bin / "conda").unlink()
        conda = self.scratch / "custom/bin/conda"
        self.program(conda, 'printf invoked > "$HOME/tool-invocations"\nexit 99\n')
        self.env["CONDA_EXE"] = str(conda)
        result = self.guard("pip install pandas")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("conda install -c conda-forge <packages>", result.stderr)
        self.assertFalse((self.home / "tool-invocations").exists())
        conda.unlink()
        self.assertAllowed(self.guard("pip install pandas"))

    def test_plain_hook_runs_without_filesystem_patching(self):
        self.prefer("conda-forge")
        result = self.guard("pip install pandas", isolate_system=False)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "Use conda install -c conda-forge <packages> instead.\n")

    def test_each_install_group_is_allowed_only_by_its_own_preference(self):
        replacements = {
            "conda-forge": "conda install -c conda-forge",
            "uv": "uv add", "pixi": "pixi add", "pip-venv": "python3 -m pip install",
        }
        for preferred in INSTALLS:
            self.prefer(preferred)
            for group, commands in INSTALLS.items():
                for command in commands:
                    with self.subTest(preferred=preferred, command=command):
                        result = self.guard(command)
                        if group == preferred:
                            self.assertAllowed(result)
                        else:
                            self.assertEqual(result.returncode, 2, result.stderr)
                            self.assertEqual(result.stdout, "")
                            self.assertIn(replacements[preferred] + " <packages>", result.stderr)
                            if preferred == "pip-venv":
                                self.assertIn("venv", result.stderr)

    def test_project_files_allow_only_their_own_tool_from_the_payload_cwd(self):
        for filename, own_command, other_command, preference in (
            ("uv.lock", "uv sync", "pixi add pandas", "conda-forge"),
            ("environment.yml", "conda install pandas", "pip install pandas", "uv"),
            ("environment.yml", "mamba install pandas", "pixi add pandas", "pip-venv"),
            ("pixi.toml", "pixi add pandas", "uv add pandas", "conda-forge"),
            ("pixi.lock", "pixi install", "pip install pandas", "conda-forge"),
        ):
            with self.subTest(filename=filename, command=own_command):
                self.prefer(preference)
                marker = self.project / filename
                marker.touch()
                self.assertAllowed(self.guard(own_command))
                self.assertEqual(self.guard(other_command).returncode, 2)
                marker.unlink()
                self.assertEqual(self.guard(own_command).returncode, 2)
                # The hook process runs in scratch HOME, not in payload cwd.
                (self.home / filename).touch()
                self.assertEqual(self.guard(own_command).returncode, 2)
                (self.home / filename).unlink()

    def test_missing_preferred_tool_allows_every_install_group(self):
        for preferred, tool in (("conda-forge", "conda"), ("uv", "uv"),
                                ("pixi", "pixi"), ("pip-venv", "pip")):
            with self.subTest(preferred=preferred):
                self.prefer(preferred)
                (self.bin / tool).unlink()
                for commands in INSTALLS.values():
                    for command in commands:
                        self.assertAllowed(self.guard(command))
                self.program(tool, "exit 99\n")

    def test_no_preference_or_other_choices_never_refuse_commands(self):
        for commands in INSTALLS.values():
            for command in commands:
                self.assertAllowed(self.guard(command))
        path = self.repo / "fleet/preferences/user.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"claude": {
            "python": "another-python", "environment_manager": "other-manager",
        }}), encoding="utf-8")
        for command in ("pip install pandas", "python3 app.py", "conda create -n demo"):
            self.assertAllowed(self.guard(command))

    def test_unrelated_commands_interpreters_and_environment_managers_are_allowed(self):
        commands = (
            "git status", "npm install", "echo pip install pandas",
            "printf '%s' 'pip install pandas'", "python3 app.py", "python -V",
            "python3 -m venv demo", "conda create -n demo python", "conda activate demo",
            "mamba env create", "uv venv", "uv python install", "pixi shell",
            "pip list", "pip uninstall pandas", "uv remove pandas", "conda info",
            "/usr/bin/pip install pandas", "./install-packages.sh",
        )
        for preferred in INSTALLS:
            self.prefer(preferred)
            for command in commands:
                with self.subTest(preferred=preferred, command=command):
                    self.assertAllowed(self.guard(command))

    def test_malformed_payloads_fail_open(self):
        self.prefer("conda-forge")
        for payload in ("not json", "null", "[]", "{}", json.dumps({
            "tool_name": "Bash", "tool_input": {"command": "pip install 'unterminated"},
            "cwd": str(self.project),
        }), json.dumps({"tool_name": "Bash", "tool_input": []}), json.dumps({
            "tool_name": "Bash", "tool_input": {"command": None}, "cwd": [],
        }), json.dumps({"tool_name": "Edit", "tool_input": {"command": "pip install pandas"}})):
            with self.subTest(payload=payload):
                self.assertAllowed(self.run_payload(payload))

    def test_preference_load_errors_fail_open(self):
        self.prefer("conda-forge")
        path = self.repo / "fleet/preferences/user.json"
        for content in (b"{invalid", b"\xff", b'{"claude": {"python_install": "unknown"}}'):
            path.write_bytes(content)
            self.assertAllowed(self.guard("pip install pandas"))
        self.prefer("conda-forge")
        self.program("uname", "exit 1\n")
        self.assertAllowed(self.guard("pip install pandas"))

    def test_machine_preference_and_running_os_control_the_guard(self):
        self.prefer("conda-forge")
        self.prefer("uv", "machines/linux.json")
        self.assertEqual(self.guard("pip install pandas").returncode, 2)
        self.assertAllowed(self.guard("conda install pandas"))
        self.program("uname", "printf 'Linux\\n'\n")
        self.assertAllowed(self.guard("uv add pandas"))
        result = self.guard("conda install pandas")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("uv add <packages>", result.stderr)

    def test_guard_never_executes_payload_or_changes_files(self):
        self.prefer("conda-forge")
        snapshot = lambda: {str(p.relative_to(self.scratch)): p.read_bytes()
                            for p in self.scratch.rglob("*") if p.is_file()}
        before = snapshot()
        self.assertEqual(self.guard("pip install pandas").returncode, 2)
        self.assertAllowed(self.guard("touch should-not-exist"))
        self.assertAllowed(self.guard("conda install pandas"))
        self.assertEqual(snapshot(), before)

    def test_shell_lists_check_install_commands_and_keep_syntax_out_of_replacements(self):
        self.prefer("conda-forge")
        for command in (
            "true && pip install pandas", "pip install pandas && git status",
            "git status; pip3 install pandas", "false || uv add pandas",
            "git status; python3 -m pip install pandas",
        ):
            with self.subTest(command=command):
                result = self.guard(command)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stderr, "Use conda install -c conda-forge <packages> instead.\n")
                for unrelated in ("git", "true", "false", "tee", "&&", "||", "install.log"):
                    self.assertNotIn(unrelated, result.stderr)
        for command in (
            "echo '&&' pip install pandas", 'echo "pip install pandas; uv sync"',
            "printf '%s' 'a\npip install pandas'", "cat <<'EOF'\npip install pandas\nEOF",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.guard(command))

    def test_cd_before_an_install_allows_the_whole_command_unjudged(self):
        self.prefer("conda-forge")
        for command in (
            "cd uv-project && uv sync", "cd uv-project && pip install pandas",
            "pip install pandas && cd project && uv sync",
            "cd project || pip install pandas", "cd project; pip install pandas",
            "cd /uv-project | cat; uv sync", "cd /uv-project & uv sync",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.guard(command))

    def test_directory_stack_and_builtin_cd_allow_later_installs_unjudged(self):
        self.prefer("conda-forge")
        destination = self.project / "uv-project"
        destination.mkdir()
        (destination / "uv.lock").touch()
        for command in (
            "pushd uv-project && uv sync", "builtin cd uv-project && uv sync",
            "popd && uv sync", "pushd uv-project; pip install pandas",
            "builtin cd uv-project || pip install -q pandas",
            "pip install pandas && popd && uv sync",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.guard(command))

    def test_unknown_options_and_adjacent_quoted_arguments_are_allowed_unjudged(self):
        self.prefer("conda-forge")
        for command in (
            "pip install --index-url https://example.invalid/simple pandas numpy",
            "pip install --index-url=https://example.invalid/simple pandas numpy",
            "uv add --dev pandas numpy", "pixi add --feature test pandas numpy",
            "pip install --only-binary :all: pandas", "pip install --root-user-action ignore pandas",
            'pip install "pandas""[performance]"', 'pip install "foo"bar',
            'pip install foo"bar"', "pip install pandas && uv add --group test numpy",
            "pip install -q --index-url X pandas", "pip install --quiet=true pandas",
            "pip install -qU pandas",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.guard(command))
        result = self.guard('pip install "pandas>=2"')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("conda install -c conda-forge <packages>", result.stderr)

    def test_known_value_free_flags_do_not_bypass_a_conflicting_preference(self):
        self.prefer("conda-forge")
        for flag in ("-q", "--quiet", "-U", "--upgrade", "--user", "--no-cache-dir",
                     "-y", "--yes", "--dry-run", "-v", "--verbose", "-q -U --user"):
            for prefix in ("pip install", "pip3 install", "python -m pip install",
                           "python3 -m pip install", "uv pip install", "uv add", "pixi add"):
                with self.subTest(flag=flag, prefix=prefix):
                    result = self.guard(f"{prefix} {flag} pandas")
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "Use conda install -c conda-forge <packages> instead.\n")
        result = self.guard("true && pip install -q pandas")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertAllowed(self.guard("pip install -q --index-url X pandas"))
        self.prefer("pip-venv")
        self.assertAllowed(self.guard("python3 -m pip install -q -U pandas"))
        for command in ("conda install -y pandas", "mamba install --yes pandas",
                        "uv sync --quiet", "pixi install --verbose"):
            with self.subTest(command=command):
                result = self.guard(command)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("python3 -m pip install <packages> inside a venv", result.stderr)

    def test_uncertain_shell_constructs_allow_the_whole_command_unjudged(self):
        self.prefer("conda-forge")
        for command in (
            "pip install pandas | tee install.log", "pip install pandas & echo done",
            "pip install pandas && cat <<EOF", "cat <<EOF\ndata\nEOF\npip install pandas",
            "pip install $(printf pandas)", "pip install `printf pandas`",
            "git status\npip install pandas", "pip install pandas\ngit status",
            "echo ok # comment\npip install pandas", "pip install pandas # comment",
            "pip install pandas && echo 'unterminated", "pip install pandas && echo $(date)",
            "pip install pandas && cat | tee log", "pip install pandas; echo ok &",
            "pip install pandas > install.log", "pip install pandas 2> error.log",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.guard(command))

    def test_parameter_expansions_are_allowed_without_interpreting_their_contents(self):
        self.prefer("conda-forge")
        for command in (
            "echo ${x:-foo; pip install pandas;}",
            "echo ${x:-foo && pip install pandas}",
            "pip install pandas && echo ${x:-default}",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.guard(command))

    def test_quoted_shell_operators_and_hashes_are_not_syntax(self):
        self.prefer("conda-forge")
        for command in (
            "echo '&&' || pip install pandas", 'echo "|"; pip install pandas',
            "echo '# comment'; pip install pandas", "pip install pandas && echo ';'",
        ):
            with self.subTest(command=command):
                result = self.guard(command)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("conda install -c conda-forge <packages>", result.stderr)


if __name__ == "__main__":
    unittest.main()
