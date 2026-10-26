#!/usr/bin/env python3
"""Tests for scripts/restore-agents.py.

The command reads a selected or newest tmux-resurrect snapshot, works out which
panes were running an agent, and resumes each one into the window it came from. These tests
drive its command line as a subprocess and assert on what a caller sees: the exit
code and the plan it prints. Nothing imports the command's internals, so a later
refactor is free as long as the accept/skip table behaves the same (shyrosa#30's
testing decisions).

Isolation is two facts, both established by the orchestrator's tests in the
sitting before this one. HOME points at a scratch directory, which is where both
inputs live: the resurrect snapshot under ~/.local/share and the claude
transcripts under ~/.claude. And a throwaway tmux server stands up with TMUX
unset and TMUX_TMPDIR aimed at scratch, so the live one is never seen. No
test-only argument is added to the command; the seam is the command line and the
scratch home behind it. Every test reaps its own server in tearDown, including on
failure, so the default socket is never touched.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_CMD = os.path.join(_HERE, "restore-agents.py")


def _encode_project(cwd):
    """Claude Code's project-dir name for a working directory: every non-word
    character becomes a dash. The command reads cwd from inside each transcript
    rather than trusting this, so the exact scheme only has to be plausible."""
    return "".join(c if c.isalnum() else "-" for c in cwd)


class RestoreBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="restore-test-")
        self.home = os.path.join(self.tmpdir, "home")
        self.resurrect_dir = os.path.join(self.home, ".local", "share", "tmux", "resurrect")
        self.projects_dir = os.path.join(self.home, ".claude", "projects")
        os.makedirs(self.resurrect_dir)
        os.makedirs(self.projects_dir)
        # Load before the first pane starts; later windows inherit this too.
        self.tmux_config = os.path.join(self.tmpdir, "tmux.conf")
        with open(self.tmux_config, "w") as fh:
            fh.write("set-option -g default-shell /bin/sh\n")
        # Every firing runs a synthetic CLI, never an installed agent. Capture
        # argv after shell parsing so tests can check what the agent receives.
        self.bin = os.path.join(self.tmpdir, "bin")
        os.makedirs(self.bin)
        self.argv_path = os.path.join(self.home, "restored-argv.json")
        fake = os.path.join(self.bin, "claude")
        with open(fake, "w") as fh:
            fh.write("#!%s\nimport json, os, sys\n" % sys.executable)
            fh.write("with open(%r, 'w') as fh: json.dump(sys.argv[1:], fh)\n" %
                     (self.argv_path + ".tmp"))
            fh.write("os.replace(%r, %r)\n" %
                     (self.argv_path + ".tmp", self.argv_path))
        os.chmod(fake, 0o755)

        self.socket = os.path.join(self.tmpdir, "tmux-%d" % os.getuid(), "default")
        self._panes = []   # pane rows for the snapshot
        self._windows = {}  # (session, window_index) -> window_name
        self._session_started = set()

    def tearDown(self):
        subprocess.run(
            ["tmux", "kill-server"],
            env=self._server_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # -- tmux plumbing, isolated the way the orchestrator's tests do it --------

    def _server_env(self):
        env = dict(os.environ)
        env.pop("TMUX", None)
        env.pop("XDG_DATA_HOME", None)
        env["TMUX_TMPDIR"] = self.tmpdir
        env["HOME"] = self.home
        path = env.get("PATH", "")
        env["PATH"] = self.bin + os.pathsep + path
        return env

    def _tmux(self, *args, check=True):
        proc = subprocess.run(
            ["tmux", *args],
            env=self._server_env(),
            capture_output=True,
            text=True,
        )
        if check and proc.returncode != 0:
            self.fail("tmux %s failed: %s" % (" ".join(args), proc.stderr))
        return proc.stdout

    def _fake_claude(self):
        """A binary named claude, so a pane running it reports its command as
        `claude`. It has to be a freshly built binary: a copied one loses its
        signature and macOS kills it, and a script or symlink reports the
        interpreter's name, not claude. Compiled here, it just blocks."""
        dst = os.path.join(self.bin, "claude")
        cc = shutil.which("cc") or shutil.which("clang")
        if not cc:
            self.skipTest("no C compiler to build a fake claude binary")
        proc = subprocess.run(
            [cc, "-x", "c", "-o", dst, "-"],
            input="#include <unistd.h>\nint main(void){pause();return 0;}\n",
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            self.skipTest("could not compile a fake claude binary: %s" % proc.stderr)
        return dst

    def _wait_command(self, target, expected, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            got = self._tmux(
                "display-message", "-p", "-t", target, "#{pane_current_command}"
            ).strip()
            if got == expected:
                return
            time.sleep(0.1)
        self.fail("pane %s never reached command %r (last: %r)" % (target, expected, got))

    # -- building a synthetic board -------------------------------------------

    def add_window(self, session, window_name):
        """Create the window (and the session on first use) and return its live
        coordinates, so the snapshot we later write lines up with the server."""
        if session not in self._session_started:
            self._tmux("-f", self.tmux_config,
                       "new-session", "-d", "-s", session, "-n", window_name,
                       "-x", "120", "-y", "40")
            self._session_started.add(session)
        else:
            self._tmux("new-window", "-t", "%s:" % session, "-n", window_name)
        target = "%s:%s" % (session, window_name)
        win_index = self._tmux(
            "display-message", "-p", "-t", target, "#{window_index}"
        ).strip()
        pane_index = self._tmux(
            "display-message", "-p", "-t", target, "#{pane_index}"
        ).strip()
        self._windows[(session, win_index)] = window_name
        return win_index, pane_index

    def _snapshot_target(self, session, window_name, pane_index):
        return "%s:%s.%s" % (session, window_name, pane_index)

    def add_agent(self, session, window_name, name, cwd, launch="claude", live="shell"):
        """Record an agent pane in the snapshot and set the matching live pane's
        state. live is 'shell' (fresh prompt), 'claude' (already an agent), or a
        command string to run so the pane holds that process (a pager, say)."""
        win_index, pane_index = self.add_window(session, window_name)
        target = "%s:%s" % (session, window_name)
        if live == "claude":
            # Run the fake by absolute path so a fish `claude` function cannot
            # shadow it into launching a real agent; the process is named claude.
            self._tmux("send-keys", "-t", target, self._fake_claude(), "Enter")
            self._wait_command(target, "claude")
        elif live != "shell":
            self._tmux("send-keys", "-t", target, live, "Enter")
            self._wait_command(target, live.split()[0])
        self._panes.append({
            "session": session, "window_index": win_index, "pane_index": pane_index,
            "title": "✳ " + name, "cwd": cwd,
            "current_command": "claude.exe", "full_command": launch,
        })
        return self._snapshot_target(session, window_name, pane_index)

    def add_shell(self, session, window_name, cwd):
        """A pane recorded as a plain shell: it must never be restored."""
        win_index, pane_index = self.add_window(session, window_name)
        self._panes.append({
            "session": session, "window_index": win_index, "pane_index": pane_index,
            "title": "~", "cwd": cwd,
            "current_command": "fish", "full_command": "",
        })
        return self._snapshot_target(session, window_name, pane_index)

    def write_snapshot(self):
        lines = []
        for p in self._panes:
            full = (":" + p["full_command"]) if p["full_command"] else ":"
            lines.append("\t".join([
                "pane", p["session"], p["window_index"], "1", ":*", p["pane_index"],
                p["title"], ":" + p["cwd"], "1", p["current_command"], full,
            ]))
        for (session, win_index), name in self._windows.items():
            lines.append("\t".join([
                "window", session, win_index, ":" + name, "1", ":*",
                "abcd,120x40,0,0,0", "off",
            ]))
        with open(os.path.join(self.resurrect_dir, "last"), "w") as fh:
            fh.write("\n".join(lines) + "\n")

    def make_transcript(self, name, cwd, session_id, age_seconds=0):
        """A claude transcript file whose header carries the agent name and cwd,
        aged by age_seconds so mtime ordering is under the test's control."""
        proj = os.path.join(self.projects_dir, _encode_project(cwd))
        os.makedirs(proj, exist_ok=True)
        path = os.path.join(proj, session_id + ".jsonl")
        rows = [
            {"type": "custom-title", "customTitle": name, "sessionId": session_id},
            {"type": "agent-name", "agentName": name, "sessionId": session_id},
            {"type": "user", "cwd": cwd, "sessionId": session_id},
        ]
        with open(path, "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        when = time.time() - age_seconds
        os.utime(path, (when, when))
        return path

    # -- driving the command ---------------------------------------------------

    def run_cmd(self, *args):
        self.write_snapshot()
        return subprocess.run(
            ["python3", _CMD, *args],
            env=self._server_env(),
            capture_output=True,
            text=True,
        )

    def pane_text(self, target, lines=30):
        return self._tmux("capture-pane", "-p", "-t", target, "-S", "-%d" % lines)

    def restored_argv(self):
        deadline = time.time() + 5
        while not os.path.exists(self.argv_path) and time.time() < deadline:
            time.sleep(0.1)
        with open(self.argv_path) as fh:
            return json.load(fh)


class InheritedFishShell(RestoreBase):
    def _server_env(self):
        return dict(super()._server_env(), SHELL=os.path.join(self.bin, "fish"))

    def test_first_pane_and_later_window_ignore_inherited_shell_startup(self):
        # Stand in for a shell whose startup changes the foreground command or
        # interprets input differently, without running any installed shell config.
        marker = os.path.join(self.home, "fish-started")
        fish = os.path.join(self.bin, "fish")
        with open(fish, "w") as fh:
            fh.write('#!/bin/sh\nprintf started >> "$HOME/fish-started"\nexec /bin/sh\n')
        os.chmod(fish, 0o755)

        self.add_window("proj", "first")
        self.add_window("proj", "later")
        for window in ("first", "later"):
            with self.subTest(window=window):
                target = "proj:" + window
                self.assertEqual(self._tmux(
                    "show-options", "-gv", "default-shell"
                ).strip(), "/bin/sh")
                self._tmux("send-keys", "-t", target, "cat", "Enter")
                self._wait_command(target, "cat")
                self.assertFalse(os.path.exists(marker), "inherited fish startup ran")


class DryRunPlan(RestoreBase):
    def test_plan_names_pane_and_command_and_changes_nothing(self):
        t = self.add_agent(
            "proj", "matt-flow", "matt-flow-16", "/work/proj",
            launch="claude -n matt-flow-16 --model opus --effort high "
                   "--permission-mode bypassPermissions 'rebuild the merged ticket'",
        )
        self.make_transcript("matt-flow-16", "/work/proj", "sid-flow")
        proc = self.run_cmd("--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("plan %s:" % t, proc.stdout)
        self.assertIn("claude -r sid-flow", proc.stdout)
        # A unique name never chose between candidates, so no report.
        self.assertNotIn("chose", proc.stdout)
        # The plan touches nothing: the pane holds no typed resume.
        self.assertNotIn("claude -r", self.pane_text(t))

    def test_model_effort_permission_carry_across(self):
        t = self.add_agent(
            "proj", "flow", "n1", "/work/proj",
            launch="claude -n n1 --model opus --effort high "
                   "--permission-mode bypassPermissions",
        )
        self.make_transcript("n1", "/work/proj", "sid1")
        proc = self.run_cmd("--dry-run")
        self.assertIn(
            "claude -r sid1 --model opus --effort high --permission-mode bypassPermissions",
            proc.stdout,
        )

    def test_rebuilt_command_drops_the_task_prompt(self):
        self.add_agent(
            "proj", "flow", "n1", "/work/proj",
            launch="claude -n n1 --model opus 'go rebuild the whole merged ticket now'",
        )
        self.make_transcript("n1", "/work/proj", "sid1")
        proc = self.run_cmd("--dry-run")
        self.assertNotIn("rebuild", proc.stdout)
        self.assertIn("claude -r sid1 --model opus", proc.stdout)

    def test_name_comes_from_title_not_the_launch_flags(self):
        # The launch carries no name flag at all; the title holds the name.
        self.add_agent("proj", "flow", "titled-agent", "/work/proj", launch="claude")
        self.make_transcript("titled-agent", "/work/proj", "sid-title")
        proc = self.run_cmd("--dry-run")
        self.assertIn("claude -r sid-title", proc.stdout)


class SnapshotSelection(RestoreBase):
    def test_older_snapshot_can_be_selected_without_repointing_last(self):
        target = self.add_agent(
            "proj", "flow", "n1", "/work/proj", launch="claude --model opus"
        )
        self.make_transcript("n1", "/work/proj", "sid-old-snapshot")
        self.write_snapshot()
        last = os.path.join(self.resurrect_dir, "last")
        older = os.path.join(self.resurrect_dir, "tmux_resurrect_20260822T220000.txt")
        os.rename(last, older)
        # Continuum saved again while the agent was absent.
        self._panes[0]["current_command"] = "bash"

        proc = self.run_cmd("--dry-run", "--snapshot", older)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("plan %s: claude -r sid-old-snapshot --model opus" % target,
                      proc.stdout)
        self.assertNotIn("claude -r", self.pane_text(target))
        default = self.run_cmd("--dry-run")
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertEqual(default.stdout.strip(), "nothing to restore")

    def test_selected_snapshot_restores_only_the_requested_session(self):
        target = self.add_agent("proja", "flow", "a1", "/work/a")
        other = self.add_agent("projb", "flow", "b1", "/work/b")
        self.make_transcript("a1", "/work/a", "sid-a")
        self.make_transcript("b1", "/work/b", "sid-b")
        self.write_snapshot()
        older = os.path.join(self.tmpdir, "older snapshot.txt")
        os.rename(os.path.join(self.resurrect_dir, "last"), older)
        self._panes.clear()

        proc = self.run_cmd("--snapshot", older, "--session", "proja")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("restored %s: claude -r sid-a" % target, proc.stdout)
        self.assertIn("claude -r sid-a", self.pane_text(target))
        self.assertNotIn(other, proc.stdout)
        self.assertNotIn("claude -r", self.pane_text(other))

    def test_missing_selected_snapshot_reports_error_without_falling_back(self):
        target = self.add_agent("proj", "flow", "n1", "/work/proj")
        self.make_transcript("n1", "/work/proj", "sid1")
        missing = os.path.join(self.tmpdir, "missing.txt")

        proc = self.run_cmd("--snapshot", missing)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("error: cannot read resurrect snapshot", proc.stderr)
        self.assertIn(missing, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertNotIn("claude -r", self.pane_text(target))


class AgentVersusShell(RestoreBase):
    def test_shell_pane_is_never_in_the_plan(self):
        agent = self.add_agent("proj", "flow", "n1", "/work/proj", launch="claude -n n1")
        shell = self.add_shell("proj", "just-a-shell", "/work/proj")
        self.make_transcript("n1", "/work/proj", "sid1")
        proc = self.run_cmd("--dry-run")
        self.assertIn(agent, proc.stdout)
        self.assertNotIn(shell, proc.stdout)


class ResolveBySessionId(RestoreBase):
    def test_newest_matching_candidate_wins(self):
        t = self.add_agent("proj", "flow", "shared", "/work/proj", launch="claude -n shared")
        self.make_transcript("shared", "/work/proj", "sid-old", age_seconds=3600)
        self.make_transcript("shared", "/work/proj", "sid-new", age_seconds=10)
        proc = self.run_cmd("--dry-run")
        self.assertIn("claude -r sid-new", proc.stdout)
        self.assertNotIn("claude -r sid-old", proc.stdout)
        # Both candidates sat in the recorded directory, so this was a choice.
        self.assertIn("chose %s: 'shared' had 2 candidate sessions" % t, proc.stdout)

    def test_the_recorded_directory_separates_two_candidates(self):
        # The pane's directory decides between two sessions that share a name,
        # even against recency: the match in the recorded directory wins over a
        # newer one elsewhere.
        self.add_agent("proj", "flow", "shared", "/work/proj", launch="claude -n shared")
        self.make_transcript("shared", "/work/proj", "sid-here", age_seconds=3600)
        self.make_transcript("shared", "/elsewhere", "sid-there", age_seconds=10)
        proc = self.run_cmd("--dry-run")
        self.assertIn("claude -r sid-here", proc.stdout)
        self.assertNotIn("claude -r sid-there", proc.stdout)
        # The directory narrowed it to exactly one: no choosing, no report.
        self.assertNotIn("chose", proc.stdout)

    def test_a_name_with_no_session_is_skipped_and_reported(self):
        t = self.add_agent("proj", "flow", "ghost", "/work/proj", launch="claude -n ghost")
        proc = self.run_cmd("--dry-run")
        self.assertIn("skip %s" % t, proc.stdout)
        self.assertIn("no session named 'ghost'", proc.stdout)

    def test_candidates_that_cannot_be_narrowed_resume_the_newest_and_report_it(self):
        # Two sessions share the name, and neither sits in the pane's recorded
        # directory, so the directory cannot separate them. Rather than skip,
        # the newest resumes, and the run reports that it had to choose
        # (shyrosa#37 reverses the earlier skip-and-report-candidates ruling).
        t = self.add_agent("proj", "flow", "twin", "/work/proj", launch="claude -n twin")
        self.make_transcript("twin", "/elsewhere/a", "sid-a", age_seconds=100)
        self.make_transcript("twin", "/elsewhere/b", "sid-b", age_seconds=200)
        proc = self.run_cmd("--dry-run")
        self.assertNotIn("skip %s" % t, proc.stdout)
        self.assertIn("claude -r sid-a", proc.stdout)
        self.assertNotIn("claude -r sid-b", proc.stdout)
        self.assertIn("chose %s: 'twin' had 2 candidate sessions" % t, proc.stdout)


class ResolutionMutationGate(RestoreBase):
    """Take the oldest candidate instead of the newest: expect the plan to name
    the wrong session. This proves the newest-wins selection is load-bearing."""

    def test_oldest_instead_of_newest_changes_the_plan(self):
        self.add_agent("proj", "flow", "shared", "/work/proj", launch="claude -n shared")
        self.make_transcript("shared", "/work/proj", "sid-old", age_seconds=3600)
        self.make_transcript("shared", "/work/proj", "sid-new", age_seconds=10)
        self.write_snapshot()
        with open(_CMD) as fh:
            src = fh.read()
        needle = "max(pool, key=_mtime_of)"
        replacement = "min(pool, key=_mtime_of)"
        self.assertIn(needle, src, "selection wording moved; update this gate")
        mutant = src.replace(needle, replacement)
        mpath = os.path.join(self.tmpdir, "restore-mutant.py")
        with open(mpath, "w") as fh:
            fh.write(mutant)
        proc = subprocess.run(
            ["python3", mpath, "--dry-run"],
            env=self._server_env(),
            capture_output=True,
            text=True,
        )
        self.assertIn("claude -r sid-old", proc.stdout)
        self.assertNotIn("claude -r sid-new", proc.stdout)


class AlreadyRunning(RestoreBase):
    def test_pane_already_running_an_agent_is_skipped(self):
        t = self.add_agent("proj", "flow", "n1", "/work/proj",
                           launch="claude -n n1", live="claude")
        self.make_transcript("n1", "/work/proj", "sid1")
        proc = self.run_cmd("--dry-run")
        self.assertIn("skip %s" % t, proc.stdout)
        self.assertIn("already running an agent", proc.stdout)


class SessionFilter(RestoreBase):
    def test_filter_restricts_the_run_and_leaves_others_untouched(self):
        ta = self.add_agent("proja", "flow", "a1", "/work/a", launch="claude -n a1")
        tb = self.add_agent("projb", "flow", "b1", "/work/b", launch="claude -n b1")
        self.make_transcript("a1", "/work/a", "sid-a")
        self.make_transcript("b1", "/work/b", "sid-b")
        proc = self.run_cmd("--session", "proja")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # proja fired, projb was not even mentioned.
        self.assertIn("claude -r sid-a", proc.stdout)
        self.assertNotIn(tb, proc.stdout)
        self.assertIn("claude -r sid-a", self.pane_text(ta))
        self.assertNotIn("claude -r", self.pane_text(tb))


class NothingToRestore(RestoreBase):
    def test_says_so_and_exits_clean(self):
        self.add_shell("proj", "just-a-shell", "/work/proj")
        proc = self.run_cmd("--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("nothing to restore", proc.stdout)


class RestoreLog(RestoreBase):
    def read_log(self):
        with open(os.path.join(self.resurrect_dir, "restore-agents.log"), encoding="utf-8") as fh:
            return fh.read()

    def test_selected_older_snapshot_and_its_decisions_are_logged(self):
        target = self.add_agent("proj", "flow", "n1", "/work/proj")
        skipped = self.add_agent("proj", "ghost", "ghost", "/work/proj")
        self.make_transcript("n1", "/work/proj", "sid-older")
        self.write_snapshot()
        last = os.path.join(self.resurrect_dir, "last")
        older = os.path.join(self.resurrect_dir, "tmux_resurrect_20260822T220000.txt")
        os.rename(last, older)
        self._panes.clear()  # The newest snapshot has no agents.

        proc = self.run_cmd("--snapshot", older)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        log = self.read_log()
        self.assertIn("snapshot: " + older, log)
        self.assertNotIn("snapshot: " + last, log)
        self.assertIn("restored %s: claude -r sid-older" % target, log)
        self.assertIn("EnterWorktree", log)
        self.assertIn("resumed history", log)
        self.assertIn("skip %s: no session named 'ghost'" % skipped, log)
        self.assertIn("claude -r sid-older", self.pane_text(target))

    def test_unattended_runs_append_timestamped_snapshot_and_decisions(self):
        target = self.add_agent("proj", "flow", "shared", "/work/proj")
        skipped = self.add_agent("proj", "ghost", "ghost", "/work/proj")
        self.make_transcript("shared", "/work/proj", "sid-old", age_seconds=100)
        self.make_transcript("shared", "/work/proj", "sid-new")
        for _ in range(2):
            proc = self.run_cmd("--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
        log = self.read_log()
        self.assertEqual(log.count("snapshot: " + os.path.join(self.resurrect_dir, "last")), 2)
        self.assertIn("chose %s: 'shared' had 2 candidate sessions" % target, log)
        self.assertIn("plan %s: claude -r sid-new" % target, log)
        self.assertIn("skip %s: no session named 'ghost'" % skipped, log)
        for line in log.splitlines():
            self.assertRegex(line, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4} ")

    def test_actual_restore_and_skip_reasons_are_logged(self):
        restored = self.add_agent("proj", "flow", "n1", "/work/proj")
        running = self.add_agent("proj", "running", "n2", "/work/proj", live="claude")
        stuck = self.add_agent("proj", "stuck", "n3", "/work/proj", live="cat")
        self.make_transcript("n1", "/work/proj", "sid1")
        self.make_transcript("n3", "/work/proj", "sid3")
        proc = self.run_cmd()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        log = self.read_log()
        self.assertIn("restored %s: claude -r sid1" % restored, log)
        self.assertIn("skip %s: already running an agent" % running, log)
        self.assertIn("skip %s: could not return the pane to a shell prompt" % stuck, log)

    def test_nothing_to_restore_is_logged(self):
        proc = self.run_cmd()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("nothing to restore", self.read_log())

    def test_missing_snapshot_error_is_logged_without_a_terminal(self):
        proc = subprocess.run(
            ["python3", _CMD], env=self._server_env(),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no resurrect snapshot found under " + self.resurrect_dir, self.read_log())

    def test_invalid_arguments_are_logged(self):
        proc = self.run_cmd("--session")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("argument --session: expected one argument", self.read_log())

    def test_unreachable_server_error_is_logged(self):
        self._panes.append({
            "session": "absent", "window_index": "0", "pane_index": "0",
            "title": "✳ n1", "cwd": "/work/proj",
            "current_command": "claude", "full_command": "claude",
        })
        proc = self.run_cmd()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("tmux list-sessions exited", self.read_log())
        self.assertIn("no tmux server is reachable", self.read_log())

    def test_snapshot_read_failure_is_logged(self):
        # A directory at `last` makes opening the selected snapshot fail.
        os.mkdir(os.path.join(self.resurrect_dir, "last"))
        proc = subprocess.run(
            ["python3", _CMD], env=self._server_env(), capture_output=True, text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        log = self.read_log()
        self.assertIn("cannot read resurrect snapshot", log)
        self.assertIn(os.path.join(self.resurrect_dir, "last"), log)
        self.assertNotIn("Traceback", proc.stderr)

    def test_unexpected_snapshot_decode_failure_is_logged(self):
        with open(os.path.join(self.resurrect_dir, "last"), "wb") as fh:
            fh.write(b"\xff")
        proc = subprocess.run(
            ["python3", _CMD], env=self._server_env(), capture_output=True, text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("restore failed", self.read_log())
        self.assertIn("UnicodeDecodeError", self.read_log())

    def test_xdg_log_records_the_resolved_snapshot(self):
        dated = os.path.join(self.resurrect_dir, "tmux_resurrect_20261025T120000.txt")
        with open(dated, "w") as fh:
            fh.write("")
        os.symlink(os.path.basename(dated), os.path.join(self.resurrect_dir, "last"))
        # Relocate the existing fixture to exercise XDG_DATA_HOME without tmux.
        data_home = os.path.join(self.home, "custom-data")
        shutil.move(os.path.join(self.home, ".local", "share"), data_home)
        env = self._server_env()
        env["XDG_DATA_HOME"] = data_home
        proc = subprocess.run(["python3", _CMD], env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.resurrect_dir = os.path.join(data_home, "tmux", "resurrect")
        self.assertIn("resolved: " + os.path.realpath(
            os.path.join(self.resurrect_dir, os.path.basename(dated))),
                      self.read_log())


class FiringLandsInThePane(RestoreBase):
    def test_resumed_agent_receives_reentry_before_its_next_build_action(self):
        injected = os.path.join(self.home, "injected")
        cwd = os.path.join(self.home, "worktree with 'quotes' $(touch %s); λ" % injected)
        self.add_agent(
            "proj", "flow", "n1", cwd,
            launch="claude --model opus --effort high "
                   "--permission-mode bypassPermissions 'rebuild the merged ticket'",
        )
        transcript = self.make_transcript("n1", cwd, "sid1")
        with open(transcript, "a") as fh:
            # Assignment is in the resumed history, not the recorded cwd or
            # the header scan used to resolve session identity.
            for _ in range(45):
                fh.write(json.dumps({"type": "user", "message": "earlier work"}) + "\n")
            fh.write(json.dumps({
                "type": "user", "message": {
                    "role": "user", "content": "EnterWorktree /work/proj/.claude/worktrees/44",
                },
            }) + "\n")
        proc = self.run_cmd()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        argv = self.restored_argv()
        self.assertEqual(argv[:8], [
            "-r", "sid1", "--model", "opus", "--effort", "high",
            "--permission-mode", "bypassPermissions",
        ])
        self.assertEqual(len(argv), 9, argv)
        prompt = argv[-1]
        self.assertIn("EnterWorktree", prompt)
        self.assertIn("resumed history", prompt)
        self.assertIn("assigned worktree", prompt)
        self.assertIn("that same worktree", prompt)
        self.assertNotIn(cwd, prompt)
        self.assertIn("before your next build action", prompt.lower())
        self.assertNotIn("rebuild the merged ticket", prompt)
        self.assertFalse(os.path.exists(injected))

    def test_unbound_agent_at_main_is_told_to_preserve_its_unbound_state(self):
        main = os.path.join(self.home, "main checkout")
        self.add_agent("proj", "director", "director", main)
        self.make_transcript("director", main, "sid-director")
        proc = self.run_cmd()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        argv = self.restored_argv()
        self.assertEqual(argv[:2], ["-r", "sid-director"])
        self.assertEqual(len(argv), 3, argv)
        prompt = argv[-1]
        self.assertIn("If you were unbound, remain unbound", prompt)
        self.assertIn("do not create a worktree or bind the main checkout", prompt)
        self.assertNotIn(main, prompt)

    def test_the_resume_reaches_the_pane_without_starting_an_agent(self):
        # The synthetic CLI exits after recording argv. Reading the pane back
        # also finds the resume that was sent.
        t = self.add_agent("proj", "flow", "n1", "/work/proj",
                           launch="claude -n n1 --model opus")
        self.make_transcript("n1", "/work/proj", "sid1")
        proc = self.run_cmd()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        time.sleep(0.5)
        self.assertIn("claude -r sid1 --model opus", self.pane_text(t))


class PagerBeforeThePrompt(RestoreBase):
    def test_a_pane_holding_a_pager_is_returned_to_its_shell_first(self):
        # resurrect leaves the pane in a pager; the resume must land in the shell
        # behind it, not in the pager.
        t = self.add_agent("proj", "flow", "n1", "/work/proj",
                           launch="claude -n n1", live="less /etc/hosts")
        self.make_transcript("n1", "/work/proj", "sid1")
        proc = self.run_cmd()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        time.sleep(0.5)
        self.assertIn("claude -r sid1", self.pane_text(t))

    def test_a_pane_that_cannot_reach_a_shell_is_skipped_not_typed_into(self):
        # cat swallows keystrokes and never quits on q, so the pane cannot be
        # returned to a prompt. Nothing must be typed into it.
        t = self.add_agent("proj", "flow", "n1", "/work/proj",
                           launch="claude -n n1", live="cat")
        self.make_transcript("n1", "/work/proj", "sid1")
        proc = self.run_cmd()
        self.assertIn("skip %s" % t, proc.stdout)
        self.assertIn("shell prompt", proc.stdout)
        self.assertNotIn("claude -r", self.pane_text(t))


if __name__ == "__main__":
    unittest.main()
