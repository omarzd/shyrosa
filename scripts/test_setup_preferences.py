#!/usr/bin/env python3
"""Run the optional wizard as a person would, in a synthetic checkout (#141).

The process, scratch checkout, PATH, HOME and typed answers are spec #135's
confirmed seams. No Claude process or real tool install is needed.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parent.parent


class SetupPreferences(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="shyrosa-141-")
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.repo = self.scratch / "shyrosa"
        (self.repo / "scripts").mkdir(parents=True)
        for name in ("preferences.py", "setup-preferences.py"):
            source = REPO / "scripts" / name
            if source.exists():
                shutil.copy2(source, self.repo / "scripts" / name)
        self.home = self.scratch / "home"
        self.home.mkdir()
        self.bin = self.scratch / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin),
                        PYTHONDONTWRITEBYTECODE="1")
        self.uname("Darwin")
        for tool in ("conda", "pip", "uv", "pixi", "claude"):
            self.program(tool, f"printf '%s\\n' '{tool}' >> '{self.scratch}/tool-calls'\nexit 99\n")
        self.settings = self.repo / "fleet/settings.json"
        self.put("fleet/settings.json", {
            "model": "opus", "env": {"EXAMPLE": "keep"},
            "hooks": {"SessionStart": [{"hooks": [{"command": "keep-me"}]}]},
            "permissions": {"deny": ["AskUserQuestion"]}, "cleanupPeriodDays": 36500,
        })

    def program(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def uname(self, kind):
        self.program("uname", f"printf '%s\\n' '{kind}'\n")

    def put(self, name, document):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def document(self, name):
        return json.loads((self.repo / name).read_text(encoding="utf-8"))

    def wizard(self, answers):
        return subprocess.run(
            [sys.executable, str(self.repo / "scripts/setup-preferences.py")],
            input=answers, cwd=self.home, env=self.env,
            capture_output=True, text=True, timeout=10,
        )

    def start_wizard(self):
        process = subprocess.Popen(
            [sys.executable, str(self.repo / "scripts/setup-preferences.py")],
            cwd=self.home, env=self.env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
        )
        self.addCleanup(self.stop_wizard, process)
        return process

    @staticmethod
    def stop_wizard(process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)

    def wait_for_prompt(self, process, marker):
        output = b""
        deadline = time.monotonic() + 10
        while marker not in output:
            remaining = deadline - time.monotonic()
            self.assertGreater(remaining, 0, "wizard did not reach the prompt")
            ready, _, _ = select.select([process.stdout], [], [], remaining)
            self.assertTrue(ready, "wizard did not reach the prompt")
            chunk = os.read(process.stdout.fileno(), 4096)
            self.assertTrue(chunk, "wizard exited before the prompt")
            output += chunk
        return output

    def effective(self):
        result = subprocess.run(
            [sys.executable, str(self.repo / "scripts/preferences.py"), "--print"],
            cwd=self.home, env=self.env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def snapshot(self):
        return {p.relative_to(self.scratch): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.scratch.rglob("*") if p.is_file()}

    def test_typed_user_answers_round_trip_and_only_the_settings_model_changes(self):
        before = self.document("fleet/settings.json")
        result = self.wizard("conda-forge\nconda\npython3\n\n\n\nsonnet\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = {"claude": {
            "python_install": "conda-forge", "environment_manager": "conda",
            "python": "python3",
        }}
        self.assertEqual(self.document("fleet/preferences/user.json"), expected)
        self.assertEqual(self.effective(), expected)
        self.assertFalse((self.repo / "fleet/preferences/machines").exists())
        before["model"] = "sonnet"
        self.assertEqual(self.document("fleet/settings.json"), before)

    def test_settings_changed_during_prompts_keep_every_key_except_the_chosen_model(self):
        process = self.start_wizard()
        process.stdin.write(b"uv\nvenv\npython3\n\n\n\n")
        self.wait_for_prompt(process, b"Claude model [opus]: ")
        latest = self.document("fleet/settings.json")
        latest["env"]["OTHER_SESSION"] = "new-value"
        latest["hooks"] = {"SessionStart": [{"hooks": [{"command": "new-hook"}]}]}
        latest["new_setting"] = {"enabled": True}
        del latest["cleanupPeriodDays"]
        self.put("fleet/settings.json", latest)
        _, stderr = process.communicate(input=b"sonnet\n", timeout=10)
        self.assertEqual(process.returncode, 0, stderr.decode())
        latest["model"] = "sonnet"
        self.assertEqual(self.document("fleet/settings.json"), latest)

    def test_failed_write_preserves_complete_json_and_removes_temporary_files(self):
        for name in ("user.json", "machines/darwin.json", "../settings.json"):
            with self.subTest(file=name):
                self.put("fleet/preferences/user.json", {"claude": {"python_install": "uv"}})
                self.put("fleet/preferences/machines/darwin.json", {"claude": {"python_install": "uv"}})
                self.put("fleet/settings.json", {"model": "opus", "other": "keep"})
                target = self.repo / "fleet/preferences" / name
                document = json.loads(target.read_text())
                document["future"] = {"padding": "x" * 16384}
                target.write_text(json.dumps(document))
                before = hashlib.sha256(target.read_bytes()).hexdigest()
                files_before = {p.relative_to(self.repo) for p in (self.repo / "fleet").rglob("*") if p.is_file()}

                def limit_write_size():
                    resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))

                result = subprocess.run(
                    [sys.executable, str(self.repo / "scripts/setup-preferences.py")],
                    input="pixi\n\n\npixi\n\n\nsonnet\n", cwd=self.home, env=self.env,
                    preexec_fn=limit_write_size, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)
                self.assertEqual(json.loads(target.read_text()), document)
                self.assertNotIn("No files changed", result.stderr)
                self.assertEqual({p.relative_to(self.repo) for p in (self.repo / "fleet").rglob("*") if p.is_file()}, files_before)

    def test_interrupt_during_save_keeps_complete_files_and_does_not_claim_no_changes(self):
        settings = self.document("fleet/settings.json")
        settings["padding"] = "x" * (64 * 1024 * 1024)
        self.put("fleet/settings.json", settings)
        before = hashlib.sha256(self.settings.read_bytes()).hexdigest()
        process = self.start_wizard()
        process.stdin.write(b"uv\nvenv\npython3\n\n\n\n")
        self.wait_for_prompt(process, b"Claude model [opus]: ")
        process.stdin.write(b"sonnet\n")
        deadline = time.monotonic() + 10
        fleet = self.repo / "fleet"
        while not any(p != self.settings and p.is_file() for p in fleet.iterdir()):
            self.assertIsNone(process.poll(), "wizard exited before a temporary settings file appeared")
            self.assertLess(time.monotonic(), deadline, "no temporary settings file appeared")
            time.sleep(0.001)
        process.send_signal(signal.SIGSTOP)
        process.send_signal(signal.SIGINT)
        process.send_signal(signal.SIGCONT)
        _, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 1, stderr.decode())
        self.assertEqual(self.document("fleet/preferences/user.json"), {"claude": {
            "python_install": "uv", "environment_manager": "venv", "python": "python3",
        }})
        self.assertNotIn("No files changed", stderr.decode())
        self.assertEqual(hashlib.sha256(self.settings.read_bytes()).hexdigest(), before)
        self.assertEqual([p for p in fleet.iterdir() if p.is_file()], [self.settings])

    def test_interrupt_at_a_prompt_truthfully_reports_no_changes(self):
        before = self.snapshot()
        process = self.start_wizard()
        self.wait_for_prompt(process, b"User: Python package install")
        process.send_signal(signal.SIGINT)
        _, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 1, stderr.decode())
        self.assertIn("No files changed", stderr.decode())
        self.assertEqual(self.snapshot(), before)

    def test_rerun_displays_saved_defaults_and_does_not_rewrite_unchanged_files(self):
        user = self.put("fleet/preferences/user.json", {
            "claude": {"python_install": "uv", "environment_manager": "venv", "python": "python3"},
            "future": {"choice": "preserve"},
        })
        machine = self.put("fleet/preferences/machines/darwin.json", {
            "claude": {"python_install": "pixi", "python": "python3"},
            "future": {"choice": "also-preserve"},
        })
        for path in (user, machine, self.settings):
            os.utime(path, ns=(1700000000000000000, 1700000000000000000))
        before = self.snapshot()
        result = self.wizard("\n" * 7)
        self.assertEqual(result.returncode, 0, result.stderr)
        for prompt in (
            "User: Python package install (conda-forge, uv, pip-venv, pixi) [uv]",
            "User: Environment manager [venv]", "User: Python interpreter [python3]",
            "darwin: Python package install (conda-forge, uv, pip-venv, pixi) [pixi]",
            "darwin: Environment manager [inherit: venv]",
            "darwin: Python interpreter [python3]", "Claude model [opus]",
        ):
            self.assertIn(prompt, result.stdout)
        self.assertEqual(self.snapshot(), before)

        changed = self.wizard("\n" * 6 + "sonnet\n")
        self.assertEqual(changed.returncode, 0, changed.stderr)
        after = self.snapshot()
        self.assertEqual({name for name in before if before[name] != after[name]},
                         {Path("shyrosa/fleet/settings.json")})

    def test_invalid_install_answers_retry_without_saving_an_unsupported_combination(self):
        result = self.wizard("pip\nconda\nuv-conda-forge\nuv\n\npython3\n\n\n\n\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.effective(), {"claude": {"python_install": "uv", "python": "python3"}})
        self.assertEqual(result.stdout.count("Choose one of: conda-forge, uv, pip-venv, pixi."), 3)

    def test_all_four_install_choices_are_readable_after_setup(self):
        for choice in ("conda-forge", "uv", "pip-venv", "pixi"):
            with self.subTest(choice=choice):
                result = self.wizard(choice + "\n" + "\n" * 6)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.effective(), {"claude": {"python_install": choice}})

    def test_failed_or_unsafe_uname_writes_nothing(self):
        for body in ("exit 1\n", "printf '../user'\n", "printf ''\n"):
            with self.subTest(body=body):
                self.program("uname", body)
                before = self.snapshot()
                result = self.wizard("\n" * 7)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("uname", result.stderr)
                self.assertEqual(self.snapshot(), before)

    def test_invalid_existing_files_fail_before_writing_or_echoing_their_contents(self):
        for name, contents in (
            ("fleet/settings.json", b'[]'),
            ("fleet/settings.json", b'{"model": {"key": "synthetic-secret"}}'),
            ("fleet/settings.json", b'{broken synthetic-secret'),
            ("fleet/settings.json", b'\xffsynthetic-secret'),
            ("fleet/preferences/user.json", b'{"claude": {"api_key": "synthetic-secret"}}'),
            ("fleet/preferences/machines/darwin.json", b'{"claude": {"python_install": "pip"}}'),
        ):
            with self.subTest(name=name, contents=contents):
                path = self.repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(contents)
                before = self.snapshot()
                result = self.wizard("\n" * 7)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(name, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertNotIn("synthetic-secret", result.stdout + result.stderr)
                self.assertEqual(self.snapshot(), before)
                path.unlink()

    def test_overrides_belong_to_the_detected_os_and_other_kinds_are_unchanged(self):
        result = self.wizard("conda-forge\nconda\npython3\nuv\n\n\nsonnet\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        darwin = self.repo / "fleet/preferences/machines/darwin.json"
        self.assertEqual(json.loads(darwin.read_text()), {"claude": {"python_install": "uv"}})
        self.assertEqual(self.effective(), {"claude": {
            "python_install": "uv", "environment_manager": "conda", "python": "python3",
        }})
        darwin_before = darwin.read_bytes(), darwin.stat().st_mtime_ns
        self.uname("Linux")
        result = self.wizard("\n\n\npixi\npixi\npython\n\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.document("fleet/preferences/machines/linux.json"), {"claude": {
            "python_install": "pixi", "environment_manager": "pixi", "python": "python",
        }})
        self.assertEqual((darwin.read_bytes(), darwin.stat().st_mtime_ns), darwin_before)
        self.assertEqual(self.effective(), {"claude": {
            "python_install": "pixi", "environment_manager": "pixi", "python": "python",
        }})
        self.uname("Darwin")
        self.assertEqual(self.effective(), {"claude": {
            "python_install": "uv", "environment_manager": "conda", "python": "python3",
        }})

    def test_dash_clears_user_and_model_choices_and_restores_machine_inheritance(self):
        self.put("fleet/preferences/user.json", {"claude": {
            "python_install": "conda-forge", "environment_manager": "conda", "python": "python3",
        }, "future": {"choice": "keep"}})
        self.put("fleet/preferences/machines/darwin.json", {
            "claude": {"python_install": "uv", "environment_manager": "venv", "python": "python"},
            "future": {"choice": "keep-too"},
        })
        settings_before = self.document("fleet/settings.json")
        result = self.wizard("\n-\n\n-\n-\n-\n-\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.document("fleet/preferences/user.json"), {
            "claude": {"python_install": "conda-forge", "python": "python3"},
            "future": {"choice": "keep"},
        })
        self.assertEqual(self.document("fleet/preferences/machines/darwin.json"), {
            "claude": {}, "future": {"choice": "keep-too"},
        })
        self.assertEqual(self.effective(), {"claude": {"python_install": "conda-forge", "python": "python3"}})
        del settings_before["model"]
        self.assertEqual(self.document("fleet/settings.json"), settings_before)
        before = self.snapshot()
        result = self.wizard("\n" * 7)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Claude model [none]", result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_eof_at_any_prompt_cancels_without_writing(self):
        answers = ["uv", "venv", "python", "pixi", "pixi", "python3", "sonnet"]
        for count in range(7):
            with self.subTest(completed_prompts=count):
                before = self.snapshot()
                result = self.wizard("".join(answer + "\n" for answer in answers[:count]))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("cancelled", result.stderr.lower())
                self.assertEqual(self.snapshot(), before)

    def test_blank_fresh_choices_record_no_preference_and_leave_settings_unchanged(self):
        before = self.settings.read_bytes(), self.settings.stat().st_mtime_ns
        result = self.wizard("\n" * 7)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.document("fleet/preferences/user.json"), {"claude": {}})
        self.assertEqual((self.settings.read_bytes(), self.settings.stat().st_mtime_ns), before)
        self.assertFalse((self.repo / "fleet/preferences/machines").exists())

    def test_home_and_environment_secrets_are_unused_and_no_tools_are_invoked(self):
        home_settings = self.home / ".claude/settings.json"
        home_settings.parent.mkdir()
        home_settings.write_text('{"model": "home-model", "apiKey": "synthetic-secret"}')
        (self.home / "user.json").write_text('{"claude": {"python": "home-python"}}')
        self.env["ANTHROPIC_API_KEY"] = "synthetic-secret"
        before = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        result = self.wizard("uv\nvenv\npython3\n\n\n\nsonnet\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}, before)
        self.assertFalse((self.scratch / "tool-calls").exists())
        for path in (self.repo / "fleet").rglob("*.json"):
            self.assertNotIn("synthetic-secret", path.read_text())
        self.assertNotIn("synthetic-secret", result.stdout + result.stderr)
        self.assertEqual(self.effective(), {"claude": {
            "python_install": "uv", "environment_manager": "venv", "python": "python3",
        }})


if __name__ == "__main__":
    unittest.main()
