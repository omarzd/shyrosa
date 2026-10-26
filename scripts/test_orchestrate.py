#!/usr/bin/env python3
"""Tests for overlay/tmux-orchestrator/scripts/orchestrate.sh.

These drive the script's command line as a subprocess and assert on what a
caller sees: the exit code and the text on stdout/stderr. Nothing sources the
script or reads its internal variables, so a later refactor is free as long as
the accept/reject table behaves the same. This is the exact boundary agents
call, per shyrosa#27's testing decisions.

Isolation is two environment facts, both measured in the g20 grill: running
tmux with TMUX unset and TMUX_TMPDIR pointed at a scratch dir builds a server
the live one cannot see, and setting TMUX to that server's own socket path
exercises the variable-present branch while still resolving against the
isolated server. Neither needs a change to the script. Every test stands up its
own server and reaps it in tearDown, including on failure, so the default
socket is never touched and no session is left behind.
"""
import os
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.normpath(
    os.path.join(_HERE, "..", "overlay", "tmux-orchestrator", "scripts", "orchestrate.sh")
)
_SESSION = "orch"
# The refusal a bare name earns when TMUX is absent, and the one bare `panes`
# earns; matched as substrings so the surrounding wording can move.
_BARE_TARGET_MARK = "is a bare name"
_NAME_THE_SESSION_MARK = "name the session"
_NO_SERVER_MARK = "no tmux server is reachable"
# The false diagnosis this whole ticket exists to delete.
_FORBIDDEN = "not inside a tmux session"


class OrchestrateBase(unittest.TestCase):
    """Stands up one throwaway tmux server per test and kills it afterwards."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="orch-test-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.addCleanup(self._stop_session)
        # The isolated server's default socket lives at this deterministic path
        # under our scratch TMUX_TMPDIR; the TMUX-present branch points TMUX here.
        self.socket = os.path.join(self.tmpdir, "tmux-%d" % os.getuid(), "default")
        self._tmux(
            "-f", "/dev/null", "new-session", "-d", "-s", _SESSION,
            "-x", "80", "-y", "24", "/bin/bash --noprofile --norc -i",
            check=True,
        )
        self.pane_id = self._tmux("list-panes", "-t", _SESSION, "-F", "#{pane_id}").strip()
        self.assertEqual(self.pane_id, "%0", "expected a fresh isolated server")
        self._wait_command("bash")
        self.window_id = self._tmux("list-panes", "-t", _SESSION, "-F", "#{window_id}").strip()
        self.session_id = self._tmux("list-sessions", "-F", "#{session_id}").strip()
        # The session:window.pane form the lone pane resolves to, addressed by
        # window NAME per WORKFLOW-VOCAB.md, not index; ground truth for the tests.
        self.resolved = self._tmux(
            "display-message", "-p", "-t", _SESSION,
            "#{session_name}:#{window_name}.#{pane_index}",
        ).strip()

    def _stop_session(self):
        # Kill only our named session on the isolated socket, even if setup fails.
        subprocess.run(
            ["tmux", "kill-session", "-t", "=" + _SESSION],
            env=self._server_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _wait_command(self, expected):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            got = self._tmux(
                "display-message", "-p", "-t", self.pane_id,
                "#{pane_current_command}", check=True,
            ).strip()
            if got == expected:
                return
            time.sleep(0.05)
        self.fail("pane never reached command %r (last: %r)" % (expected, got))

    def _wait_text(self, expected):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if expected in self._tmux("capture-pane", "-p", "-t", self.pane_id):
                return
            time.sleep(0.05)
        self.fail("pane never displayed %r" % expected)

    def _start_pager(self):
        path = os.path.join(self.tmpdir, "pages.txt")
        with open(path, "w") as fh:
            fh.writelines("pager-line-%03d\n" % n for n in range(200))
        less = shutil.which("less")
        if not less:
            self.skipTest("less is required for pager coverage")
        command = "LESS= LESSOPEN= %s -+F -+E %s" % (
            shlex.quote(less), shlex.quote(path),
        )
        self._tmux("send-keys", "-t", self.pane_id, "-l", "--", command, check=True)
        self._tmux("send-keys", "-t", self.pane_id, "Enter", check=True)
        self._wait_command("less")
        self._wait_text("pager-line-000")

    def _server_env(self):
        """Environment that reaches the isolated server with TMUX unset."""
        env = dict(os.environ)
        env.pop("TMUX", None)
        env["TMUX_TMPDIR"] = self.tmpdir
        return env

    def _tmux(self, *args, check=False):
        proc = subprocess.run(
            ["tmux", *args],
            env=self._server_env(),
            capture_output=True,
            text=True,
        )
        if check and proc.returncode != 0:
            self.fail("tmux %s failed: %s" % (" ".join(args), proc.stderr))
        return proc.stdout

    def run_orch(self, *args, tmux_set=False, no_server=False):
        """Run orchestrate.sh against the isolated server.

        tmux_set points TMUX at the server's socket (variable-present branch).
        no_server aims at a scratch dir with nothing listening.
        """
        env = dict(os.environ)
        env.pop("TMUX", None)
        if no_server:
            env["TMUX_TMPDIR"] = tempfile.mkdtemp(prefix="orch-empty-", dir=self.tmpdir)
        else:
            env["TMUX_TMPDIR"] = self.tmpdir
        if tmux_set:
            env["TMUX"] = "%s,0,0" % self.socket
        return subprocess.run(
            ["bash", _SCRIPT, *args],
            env=env,
            capture_output=True,
            text=True,
        )

    def assertRefused(self, proc, mark):
        out = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, "expected refusal, got success:\n" + out)
        self.assertIn(mark, out)
        self.assertNotIn(_FORBIDDEN, out)

    def assertNotRefusedAsBare(self, proc):
        self.assertNotIn(_BARE_TARGET_MARK, proc.stdout + proc.stderr)


# The six subcommands that take a <target> and share the naming rule. read and
# capture stand in for the reading side, the rest for the writing side; all six
# accept a named target with TMUX unset and refuse a bare name.
_TARGET_SUBS = ["send", "send-raw", "enter", "read", "capture", "wait-idle"]


class NamedFormsAccepted(OrchestrateBase):
    """All four unambiguous target forms run with TMUX unset."""

    def _forms(self):
        return {
            "pane_id": self.pane_id,
            "window_id": self.window_id,
            "session_id": self.session_id,
            "session_prefixed": "%s:" % _SESSION,
        }

    def test_read_accepts_every_named_form(self):
        for label, target in self._forms().items():
            with self.subTest(form=label):
                proc = self.run_orch("read", target, "5")
                self.assertNotRefusedAsBare(proc)
                self.assertEqual(proc.returncode, 0, proc.stderr)


class BareNameRefused(OrchestrateBase):
    """A bare window name is refused when TMUX is absent, for every subcommand."""

    def test_every_target_sub_refuses_bare_name(self):
        for sub in _TARGET_SUBS:
            with self.subTest(sub=sub):
                proc = self.run_orch(sub, "some-window", "hi")
                self.assertRefused(proc, _BARE_TARGET_MARK)

    def test_refusal_names_the_forms_that_work(self):
        proc = self.run_orch("read", "some-window")
        out = proc.stdout + proc.stderr
        # pane id, window id, session id, and the session:window shape.
        for token in ["%", "@", "$", ":"]:
            self.assertIn(token, out)


class BareNameAcceptedWhenTmuxSet(OrchestrateBase):
    """With TMUX set, a bare window name works exactly as before."""

    def test_read_bare_name_with_tmux_set(self):
        proc = self.run_orch("read", _SESSION, "5", tmux_set=True)
        self.assertNotRefusedAsBare(proc)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class NamedTargetsRunForEverySub(OrchestrateBase):
    """Each target-taking subcommand runs against a named target, TMUX unset."""

    def test_send_raw_named(self):
        proc = self.run_orch("send-raw", self.pane_id, "echo", "hello")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_enter_named(self):
        proc = self.run_orch("enter", self.pane_id)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_read_named(self):
        proc = self.run_orch("read", self.pane_id, "10")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_capture_named(self):
        proc = self.run_orch("capture", self.pane_id)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_wait_idle_named(self):
        # stable=1 so the idle loop returns quickly against a quiet pane.
        proc = self.run_orch("wait-idle", self.pane_id, "1", "1")
        self.assertEqual(proc.returncode, 0, proc.stderr)


class SendVerifiesWithTmuxUnset(OrchestrateBase):
    """send to a named target with TMUX unset delivers and submit-verifies."""

    def test_send_named_target_submits(self):
        proc = self.run_orch("send", self.pane_id, "echo", "verify-token")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("submitted to", proc.stdout)


class ForegroundProcessGuard(OrchestrateBase):
    """Typing refuses a pager before any text or Enter reaches it (#38)."""

    def test_send_refuses_pager_without_typing(self):
        self._assert_pager_refuses("send")

    def test_send_raw_refuses_pager_without_typing(self):
        self._assert_pager_refuses("send-raw")

    def test_enter_refuses_pager_without_typing(self):
        self._assert_pager_refuses("enter")

    def _assert_pager_refuses(self, sub):
        self._start_pager()
        before = self._tmux("capture-pane", "-p", "-t", self.pane_id)
        args = () if sub == "enter" else ("j",)
        proc = self.run_orch(sub, self.pane_id, *args)
        self.assertRefused(proc, "less")
        self.assertNotIn("submitted to", proc.stdout)
        self.assertEqual(before, self._tmux("capture-pane", "-p", "-t", self.pane_id))

    def test_shell_receives_send_raw_and_enter(self):
        proc = self.run_orch("send", self.pane_id, "printf 'shell-received:%s\\n' sent")
        self.assertEqual(proc.returncode, 0, _joined(proc))
        self.assertIn("submitted to", proc.stdout)
        self._wait_text("\nshell-received:sent")

        proc = self.run_orch("send-raw", self.pane_id, "printf 'shell-received:%s\\n' raw")
        self.assertEqual(proc.returncode, 0, _joined(proc))
        self.assertIn("sent (no enter)", proc.stdout)
        self._wait_text("' raw")
        self.assertNotIn("\nshell-received:raw", self._tmux("capture-pane", "-p", "-t", self.pane_id))

        proc = self.run_orch("enter", self.pane_id)
        self.assertEqual(proc.returncode, 0, _joined(proc))
        self.assertIn("enter ->", proc.stdout)
        self._wait_text("\nshell-received:raw")

    def test_agent_clis_receive_send_raw_and_enter(self):
        # Freshly compiled executables give tmux real foreground names without
        # running an agent. Scripts report their interpreter; copied executables
        # can fail macOS code-signing checks. Match restore-agents' fixture.
        cc = shutil.which("cc") or shutil.which("clang")
        if not cc:
            self.skipTest("a C compiler is required for synthetic agent CLIs")
        source = (
            '#include <stdio.h>\n'
            'int main(void) {\n'
            '  char line[256];\n'
            '  puts("agent-ready"); fflush(stdout);\n'
            '  while (fgets(line, sizeof line, stdin)) {\n'
            '    printf("agent-received:%s", line); fflush(stdout);\n'
            '  }\n'
            '  return 0;\n'
            '}\n'
        )
        for agent in ("claude", "claude.exe", "codex", "pi"):
            with self.subTest(agent=agent):
                path = os.path.join(self.tmpdir, agent)
                subprocess.run(
                    [cc, "-x", "c", "-o", path, "-"], input=source,
                    capture_output=True, text=True, check=True,
                )
                self._tmux("send-keys", "-t", self.pane_id, "-l", "--", shlex.quote(path), check=True)
                self._tmux("send-keys", "-t", self.pane_id, "Enter", check=True)
                self._wait_command(agent)
                self._wait_text("agent-ready")

                sent, raw = agent + "-sent", agent + "-raw"
                proc = self.run_orch("send", self.pane_id, sent)
                self.assertEqual(proc.returncode, 0, _joined(proc))
                self.assertIn("submitted to", proc.stdout)
                self._wait_text("agent-received:" + sent)

                proc = self.run_orch("send-raw", self.pane_id, raw)
                self.assertEqual(proc.returncode, 0, _joined(proc))
                self.assertIn("sent (no enter)", proc.stdout)
                self._wait_text("\n" + raw)
                self.assertNotIn("agent-received:" + raw, self._tmux("capture-pane", "-p", "-t", self.pane_id))

                proc = self.run_orch("enter", self.pane_id)
                self.assertEqual(proc.returncode, 0, _joined(proc))
                self.assertIn("enter ->", proc.stdout)
                self._wait_text("agent-received:" + raw)
                self._tmux("send-keys", "-t", self.pane_id, "C-c", check=True)
                self._wait_command("bash")


class SendClosesWithResolvedTarget(OrchestrateBase):
    """send's closing line names the resolved session, window and pane.

    Every target form used below points at the same lone pane, so each
    should close with the same resolved session:window.pane form.
    """

    def _resolved_prefix(self):
        return self.resolved

    def test_pane_id_target_resolves(self):
        proc = self.run_orch("send", self.pane_id, "echo", "verify-token")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(
            "submitted to %s: echo verify-token" % self._resolved_prefix(), proc.stdout
        )

    def test_session_prefixed_target_resolves(self):
        proc = self.run_orch("send", "%s:" % _SESSION, "echo", "verify-token")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(
            "submitted to %s: echo verify-token" % self._resolved_prefix(), proc.stdout
        )

    def test_bare_name_with_tmux_set_resolves(self):
        proc = self.run_orch("send", _SESSION, "echo", "verify-token", tmux_set=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(
            "submitted to %s: echo verify-token" % self._resolved_prefix(), proc.stdout
        )


class SendResolutionMutationGate(OrchestrateBase):
    """Return a wrong session from the resolution: expect red.

    Copies the script, swaps the resolve_target call for a hardcoded wrong
    session name, and confirms the closing line then lies about where the
    message landed. This proves SendClosesWithResolvedTarget's assertion on
    the exact resolved form is load-bearing, not a coincidental match.
    """

    def test_wrong_resolved_session_breaks_the_closing_line(self):
        with open(_SCRIPT) as fh:
            src = fh.read()
        needle = 'resolve_target "$target"'
        replacement = 'echo wrong-session:9.9'
        self.assertIn(needle, src, "resolve_target call wording moved; update this test")
        mutant = src.replace(needle, replacement)
        self.assertNotEqual(mutant, src, "mutation did not change the script")
        mpath = os.path.join(self.tmpdir, "orch-mutant-resolve.sh")
        with open(mpath, "w") as fh:
            fh.write(mutant)
        proc = subprocess.run(
            ["bash", mpath, "send", self.pane_id, "echo", "verify-token"],
            env=self._server_env(),
            capture_output=True,
            text=True,
        )
        self.assertNotIn("submitted to %s" % self.resolved, proc.stdout)


class PanesForms(OrchestrateBase):
    def test_panes_named_session_with_tmux_unset(self):
        proc = self.run_orch("panes", _SESSION)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Session: %s" % _SESSION, proc.stdout)

    def test_panes_wrong_name_fails_loudly(self):
        proc = self.run_orch("panes", "no-such-session")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no session named", proc.stdout + proc.stderr)

    def test_bare_panes_refuses_and_names_repair(self):
        proc = self.run_orch("panes")
        self.assertRefused(proc, _NAME_THE_SESSION_MARK)

    def test_bare_panes_does_not_list_every_session(self):
        # The rejected fallback would have printed a session table.
        proc = self.run_orch("panes")
        self.assertNotIn("PANE", proc.stdout)

    def test_bare_panes_works_with_tmux_set(self):
        proc = self.run_orch("panes", tmux_set=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Session: %s" % _SESSION, proc.stdout)


class NoServerReachable(OrchestrateBase):
    """With no server answering, every subcommand refuses and names that."""

    def test_every_sub_refuses_without_server(self):
        cases = [
            ("panes",),
            ("send", self.pane_id, "hi"),
            ("send-raw", self.pane_id, "hi"),
            ("enter", self.pane_id),
            ("read", self.pane_id),
            ("capture", self.pane_id),
            ("wait-idle", self.pane_id),
        ]
        for args in cases:
            with self.subTest(sub=args[0]):
                proc = self.run_orch(*args, no_server=True)
                self.assertRefused(proc, _NO_SERVER_MARK)


class TmuxMissingFromPath(OrchestrateBase):
    """With tmux off PATH, the existing refusal is unchanged."""

    def test_refuses_when_tmux_absent(self):
        bash = shutil.which("bash")
        env = dict(os.environ)
        env.pop("TMUX", None)
        env["TMUX_TMPDIR"] = self.tmpdir
        # An empty PATH hides tmux from `command -v`; bash is invoked by its own
        # absolute path so it needs no PATH to launch.
        env["PATH"] = ""
        proc = subprocess.run(
            [bash, _SCRIPT, "panes", _SESSION],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("tmux not found on PATH", proc.stdout + proc.stderr)


class NoRefusalClaimsOutsideTmux(OrchestrateBase):
    """No refusal message asserts the caller is not inside a tmux session."""

    def test_bare_target_refusal(self):
        self.assertNotIn(_FORBIDDEN, _joined(self.run_orch("read", "some-window")))

    def test_bare_panes_refusal(self):
        self.assertNotIn(_FORBIDDEN, _joined(self.run_orch("panes")))

    def test_no_server_refusal(self):
        self.assertNotIn(_FORBIDDEN, _joined(self.run_orch("panes", no_server=True)))


class MutationGate(OrchestrateBase):
    """Widen the target check to accept a bare name with TMUX absent: expect red.

    Copy the script, strip the bare-name refusal, and confirm the bare case now
    slips through. This proves BareNameRefused is load-bearing: without the
    guard, that test would go green on a call it must reject.
    """

    def test_stripping_guard_lets_bare_name_through(self):
        with open(_SCRIPT) as fh:
            src = fh.read()
        # Neuter only the bare-name refusal, by its own unique wording, so the
        # mutation is exactly the widening the guard is supposed to prevent.
        needle = 'die "target \'$t\' is a bare name'
        replacement = 'true "was a bare name'
        self.assertIn(needle, src, "bare-name guard wording moved; update this test")
        mutant = src.replace(needle, replacement)
        self.assertNotEqual(mutant, src, "mutation did not change the script")
        mpath = os.path.join(self.tmpdir, "orch-mutant.sh")
        with open(mpath, "w") as fh:
            fh.write(mutant)
        env = self._server_env()
        proc = subprocess.run(
            ["bash", mpath, "read", "some-window", "5"],
            env=env,
            capture_output=True,
            text=True,
        )
        # With the guard gone the bare name is no longer refused as such.
        self.assertNotIn(_BARE_TARGET_MARK, proc.stdout + proc.stderr)


def _joined(proc):
    return proc.stdout + proc.stderr


if __name__ == "__main__":
    unittest.main()
