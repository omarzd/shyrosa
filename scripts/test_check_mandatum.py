#!/usr/bin/env python3
"""Tests for check-mandatum.py.

The module name has a hyphen, so it can't be imported by name; load it from
its path. The config load (board line, flag path from fleet.json) now lives in
main(), so importing here runs no I/O — only the pure helpers are exercised,
the same shape as fleet/test_statusline_context.py.

These assert external behavior, not internals: a message in the new shape
passes; the old dash heading and dash lines bounce; a prose-ask bounces; a
lettered group of one bounces. When one of these breaks, check() returns a
non-empty list of break strings.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "check-mandatum.py")
_SPEC = importlib.util.spec_from_file_location(
    "check_mandatum", _SCRIPT
)
cm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cm)

BOARD_LINE = "Board updated: file:///tmp/demo-board.html"


def report(asks_block):
    """A minimal unprompted report: prose, the split, then the section."""
    return "Work done above.\n\n---\n\n" + asks_block


def check(asks_block, board_changed=None):
    return cm.check(report(asks_block), board_changed, BOARD_LINE)


NEW_HEADING = "## Mandatum? Ik Willen!"
OLD_HEADING = "## MANDATUM — Give your word whenever you're ready"


class NewHeadingPasses(unittest.TestCase):
    def test_new_heading_and_bare_command_line_passes(self):
        block = NEW_HEADING + "\n\n/wayfinder GRILL-QUEUE.md settle the pstack question"
        self.assertEqual(check(block), [])

    def test_new_heading_is_a_legal_his_section(self):
        # The new heading must be one of his sections, never bounced as a stray ##.
        self.assertIn(NEW_HEADING, cm.HIS_HEADINGS)
        self.assertEqual(cm.BLOCK_HEADING, NEW_HEADING)

    def test_triage_bare_count_line_passes(self):
        block = NEW_HEADING + "\n\n/triage 4 tickets waiting for a sitting"
        self.assertEqual(check(block), [])

    def test_pathless_ask_matt_bare_passes(self):
        block = NEW_HEADING + "\n\n/ask-matt whether the sweep touches his own prose"
        self.assertEqual(check(block), [])

    def test_pathless_log_ruling_bare_passes(self):
        block = NEW_HEADING + "\n\n/log-ruling g14"
        self.assertEqual(check(block), [])

    def test_route_after_grill_thread_arg_bounces(self):
        block = NEW_HEADING + "\n\n/route-after-grill g20"
        self.assertTrue(check(block))

    def test_implement_thread_arg_passes(self):
        block = NEW_HEADING + "\n\n/implement g20"
        self.assertEqual(check(block), [])

    def test_implement_bare_bounces(self):
        block = NEW_HEADING + "\n\n/implement"
        self.assertTrue(check(block))

    def test_handoff_with_purpose_passes(self):
        block = NEW_HEADING + "\n\n/handoff an errand pane checks the box's nvim setup"
        self.assertEqual(check(block), [])

    def test_handoff_bare_bounces(self):
        block = NEW_HEADING + "\n\n/handoff"
        self.assertTrue(check(block))

    def test_single_confirm_colon_passes(self):
        block = NEW_HEADING + "\n\nCONFIRM seams: the four sweep seams"
        self.assertEqual(check(block), [])

    def test_lettered_confirm_group_colon_passes(self):
        block = (
            NEW_HEADING
            + "\n\nCONFIRM 1a heading: the colon shape"
            + "\nCONFIRM 1b heading: the dash shape"
        )
        self.assertEqual(check(block), [])


class OldShapesBounce(unittest.TestCase):
    def test_old_dash_heading_bounces(self):
        block = OLD_HEADING + "\n\n/wayfinder GRILL-QUEUE.md settle the thing"
        self.assertTrue(check(block))

    def test_colon_command_line_bounces(self):
        block = NEW_HEADING + "\n\n/wayfinder GRILL-QUEUE.md: settle the thing"
        self.assertTrue(any("no colon on a command line" in b for b in check(block)))

    def test_mid_line_colon_command_bounces(self):
        # No colon anywhere on a command line, a time or a URL included.
        for line in ("/handoff an errand pane resumes the 14:30 deploy",
                     "/log-ruling g14 at 14:30",
                     "/handoff an errand pane checks the board:"):
            self.assertTrue(check(NEW_HEADING + "\n\n" + line), line)

    def test_glued_colon_command_bounces(self):
        block = NEW_HEADING + "\n\n/triage: 4 tickets waiting for a sitting"
        self.assertTrue(any("no colon on a command line" in b for b in check(block)))

    def test_dash_command_line_bounces(self):
        block = NEW_HEADING + "\n\n/wayfinder GRILL-QUEUE.md — settle the thing"
        self.assertTrue(check(block))

    def test_dash_triage_line_bounces(self):
        block = NEW_HEADING + "\n\n/triage — 4 tickets waiting for a sitting"
        self.assertTrue(check(block))

    def test_dash_pathless_line_bounces(self):
        block = NEW_HEADING + "\n\n/ask-matt — whether the sweep touches his prose"
        self.assertTrue(check(block))

    def test_dash_confirm_line_bounces(self):
        block = NEW_HEADING + "\n\nCONFIRM seams — the four sweep seams"
        self.assertTrue(check(block))


class StandingRulesStillHold(unittest.TestCase):
    def test_prose_ask_without_section_bounces_via_main_regex(self):
        # A prose ask dodges the section. main()'s fallback catches "say the word".
        msg = "Work is done. Say the word and I will start the sweep."
        self.assertTrue(cm.prose_ask_bounces(msg))

    def test_new_heading_present_is_not_a_prose_ask(self):
        msg = report(NEW_HEADING + "\n\n/triage 4 tickets waiting for a sitting")
        self.assertFalse(cm.prose_ask_bounces(msg))

    def test_old_heading_is_caught_by_heading_fallback(self):
        # An old or shortened heading, with the exact new heading absent, must be
        # caught so the bounce can teach the new heading.
        self.assertTrue(cm.wrong_heading(OLD_HEADING))
        self.assertTrue(cm.wrong_heading("## Mandatum"))
        self.assertFalse(cm.wrong_heading("the `## MANDATUM` section is where asks go"))

    def test_lettered_group_of_one_bounces(self):
        block = (
            NEW_HEADING
            + "\n\nCONFIRM 1a heading: the only option"
            + "\nCONFIRM 2 seams: a standalone confirm"
        )
        breaks = check(block)
        self.assertTrue(any("lettered group of one" in b for b in breaks))

    def test_empty_section_bounces(self):
        block = NEW_HEADING + "\n"
        self.assertTrue(check(block))

    def test_stray_bad_row_bounces(self):
        block = NEW_HEADING + "\n\nlet me know what you think"
        self.assertTrue(check(block))


def _scratch_root():
    d = tempfile.mkdtemp()
    os.mkdir(os.path.join(d, ".claude"))
    with open(os.path.join(d, ".claude", "fleet.json"), "w") as fh:
        json.dump({"board_html": os.path.join(d, "board.html")}, fh)
    return d


def _tree_snapshot(root):
    snap = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                snap[os.path.relpath(path, root)] = fh.read()
    return snap


def _run_text(root, message):
    return subprocess.run(
        [sys.executable, _SCRIPT, "--text", root],
        input=message,
        capture_output=True,
        text=True,
    )


PASSING_DRAFT = report(NEW_HEADING + "\n\n/triage 4 tickets waiting for a sitting")
FAILING_DRAFT = report(OLD_HEADING + "\n\n/wayfinder GRILL-QUEUE.md settle the thing")


class TextModeSubprocess(unittest.TestCase):
    def test_passing_draft_exits_0(self):
        root = _scratch_root()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root]))
        result = _run_text(root, PASSING_DRAFT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failing_draft_exits_2(self):
        root = _scratch_root()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root]))
        result = _run_text(root, FAILING_DRAFT)
        self.assertEqual(result.returncode, 2)

    def test_scratch_tree_untouched_flag_raised(self):
        root = _scratch_root()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root]))
        flag = os.path.join(root, ".claude", "board-changed")
        with open(flag, "w") as fh:
            fh.write("1")
        before = _tree_snapshot(root)
        for draft in (PASSING_DRAFT, FAILING_DRAFT):
            _run_text(root, draft)
            self.assertEqual(_tree_snapshot(root), before)

    def test_scratch_tree_untouched_flag_lowered(self):
        root = _scratch_root()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root]))
        flag = os.path.join(root, ".claude", "board-changed")
        with open(flag, "w") as fh:
            fh.write("0")
        before = _tree_snapshot(root)
        for draft in (PASSING_DRAFT, FAILING_DRAFT):
            _run_text(root, draft)
            self.assertEqual(_tree_snapshot(root), before)

    def test_defaults_root_to_cwd(self):
        root = _scratch_root()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root]))
        result = subprocess.run(
            [sys.executable, _SCRIPT, "--text"],
            input=PASSING_DRAFT,
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_crash_exits_neither_0_nor_2(self):
        # No .claude/fleet.json here, so load_config's open() raises. A crash must
        # never read as a pass or a break, so it earns its own exit code.
        root = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root]))
        result = _run_text(root, PASSING_DRAFT)
        self.assertEqual(result.returncode, 3)


class HookVersusTextParity(unittest.TestCase):
    def _run_hook(self, root, message):
        fd, transcript = tempfile.mkstemp(suffix=".jsonl")
        entry = {"type": "assistant", "message": {"content": [{"type": "text", "text": message}]}}
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(entry) + "\n")
        self.addCleanup(os.unlink, transcript)
        payload = json.dumps({"transcript_path": transcript, "stop_hook_active": False})
        return subprocess.run(
            [sys.executable, _SCRIPT, root],
            input=payload,
            capture_output=True,
            text=True,
        )

    def test_same_verdict_both_modes(self):
        # No board-changed flag in the scratch root, so hook mode also sees an
        # unjudged board claim, matching text mode's always-unjudged read.
        for draft in (PASSING_DRAFT, FAILING_DRAFT):
            root = _scratch_root()
            self.addCleanup(lambda r=root: subprocess.run(["rm", "-rf", r]))
            hook_result = self._run_hook(root, draft)
            text_result = _run_text(root, draft)
            self.assertEqual(hook_result.returncode, text_result.returncode)
            self.assertEqual(hook_result.stderr, text_result.stderr)

    def test_hook_mode_never_reads_the_flag_on_an_early_exit_message(self):
        # A message with no MANDATUM section and no board line short-circuits before
        # the section rules run — the flag read must stay behind that short-circuit
        # exactly as it did before --text, so an unreadable flag can't crash a message
        # that never needed it.
        root = _scratch_root()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root]))
        flag = os.path.join(root, ".claude", "board-changed")
        os.mkdir(flag)  # open()ing a directory raises something other than FileNotFoundError
        self.addCleanup(os.rmdir, flag)
        result = self._run_hook(root, "Nothing more to report this turn.")
        self.assertEqual(result.returncode, 0, result.stderr)



class WrongHeadingListsEveryBreak(unittest.TestCase):
    def test_wrong_heading_also_names_the_missing_line(self):
        # A bare heading and no --- line: one bounce names both, so one resend fixes both.
        msg = "Work done above.\n\n## MANDATUM\n\n/log-ruling g14"
        code, lines = cm.judge(msg, None, BOARD_LINE)
        self.assertEqual(code, 2)
        text = "\n".join(lines)
        self.assertIn("the heading is", text)
        self.assertIn("the --- line is missing", text)

    def test_wrong_heading_alone_names_only_the_heading(self):
        msg = "Work done above.\n\n---\n\n## MANDATUM\n\n/log-ruling g14"
        code, lines = cm.judge(msg, None, BOARD_LINE)
        self.assertEqual(code, 2)
        self.assertNotIn("Fix these in the same resend", "\n".join(lines))

if __name__ == "__main__":
    unittest.main()
