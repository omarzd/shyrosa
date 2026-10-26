#!/usr/bin/env python3
"""Tests for check-tells.py.

The module name has a hyphen, so it can't be imported by name; load it from its
path, the same shape as test_check_mandatum.py. The helpers are pure, so importing
runs no I/O — scan() judges a string, and the two modes are thin wrappers over it.

These assert external behavior: each tell class fires red on a dirty line and stays
green on a clean one; code fences and inline code are exempt; message mode exits 2
on a finding and 0 when clean; corpus mode exits 1 with per-file findings and 0 on a
clean sweep, and refuses an empty list so a bare glob can never stand in for one.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "check-tells.py")
_SPEC = importlib.util.spec_from_file_location(
    "check_tells", _SCRIPT
)
ct = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ct)

EM = "—"
EN = "–"
LSQUO, RSQUO, LDQUO, RDQUO = "‘", "’", "“", "”"


def messages(text):
    return [m for _line, m in ct.scan(text)]


class EmDash(unittest.TestCase):
    def test_em_dash_bounces(self):
        self.assertTrue(messages(f"the fix lands soon {EM} then we sweep"))

    def test_named_string_and_fix(self):
        [msg] = messages(f"a clause {EM} and another")
        self.assertIn(EM, msg)
        self.assertIn("comma", msg.lower())

    def test_clean_prose_passes(self):
        self.assertEqual(messages("the fix lands soon, then we sweep."), [])


class EnDash(unittest.TestCase):
    def test_en_dash_bounces(self):
        self.assertTrue(messages(f"pages 3 {EN} 9 of the log"))

    def test_no_en_dash_passes(self):
        self.assertEqual(messages("pages 3 to 9 of the log."), [])


class HyphenAsDash(unittest.TestCase):
    def test_spaced_hyphen_bounces(self):
        self.assertTrue(messages("the sweep is done - the board is clean"))

    def test_bullet_hyphen_passes(self):
        self.assertEqual(messages("- a list item that is fine"), [])

    def test_compound_hyphen_passes(self):
        self.assertEqual(messages("a well-known compound word"), [])


class CurlyQuotes(unittest.TestCase):
    def test_each_curly_quote_bounces(self):
        for ch in (LSQUO, RSQUO, LDQUO, RDQUO):
            self.assertTrue(messages(f"he said {ch}now{ch} to me"), ch)

    def test_straight_quotes_pass(self):
        self.assertEqual(messages("he said 'now' and \"later\""), [])

    def test_fix_names_the_straight_quote(self):
        [msg] = messages(f"the word {LDQUO}x")
        self.assertIn('"', msg)


class Vocab(unittest.TestCase):
    def test_worst_word_bounces(self):
        self.assertTrue(messages("let me delve into the change"))

    def test_word_is_named(self):
        [msg] = messages("this is a testament to the work")
        self.assertIn("testament", msg)

    def test_case_insensitive(self):
        self.assertTrue(messages("Crucial to the plan"))

    def test_word_boundary_holds(self):
        # 'delivery' contains no whole-word 'delve'; 'understated' is not 'underscore'.
        self.assertEqual(messages("the delivery was understated and fine."), [])


class CodeIsExempt(unittest.TestCase):
    def test_fenced_block_is_skipped(self):
        text = "clean prose here.\n```\nquoted --- dash and " + EM + " inside code\n```\nmore clean prose."
        self.assertEqual(messages(text), [])

    def test_inline_code_is_skipped(self):
        self.assertEqual(messages(f"run `git log {EM} oneline` now."), [])

    def test_prose_around_code_still_scanned(self):
        text = f"a real dash {EM} here.\n```\ncode {EM} ignored\n```"
        self.assertEqual(len(messages(text)), 1)


class ScanReportsLineNumbers(unittest.TestCase):
    def test_line_number_is_reported(self):
        text = "clean line.\nanother clean line.\ndirty " + EM + " line."
        findings = ct.scan(text)
        self.assertEqual([ln for ln, _ in findings], [3])


def _transcript(text):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    entry = {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(entry) + "\n")
    return path


class MessageMode(unittest.TestCase):
    def _run(self, message_text, stop_hook_active=False):
        path = _transcript(message_text)
        self.addCleanup(os.unlink, path)
        payload = {"transcript_path": path, "stop_hook_active": stop_hook_active}
        stdin, stderr = io.StringIO(json.dumps(payload)), io.StringIO()
        rc = ct.message_mode(["/tmp/project"], stdin=stdin, stderr=stderr)
        return rc, stderr.getvalue()

    def test_dirty_message_exits_2_and_names_the_string(self):
        rc, err = self._run(f"the work is done {EM} the board is clean")
        self.assertEqual(rc, 2)
        self.assertIn(EM, err)

    def test_clean_message_exits_0(self):
        rc, _err = self._run("the work is done, the board is clean.")
        self.assertEqual(rc, 0)

    def test_stop_hook_active_exits_0_without_scanning(self):
        rc, _err = self._run(f"a dash {EM} slips through", stop_hook_active=True)
        self.assertEqual(rc, 0)


class CorpusMode(unittest.TestCase):
    def _tree(self, files):
        d = tempfile.mkdtemp()
        paths = []
        for name, body in files.items():
            p = os.path.join(d, name)
            with open(p, "w") as fh:
                fh.write(body)
            paths.append(p)
        self.addCleanup(lambda: [os.unlink(p) for p in paths] and os.rmdir(d))
        return paths

    def test_dirty_file_exits_1_and_reports_per_file(self):
        paths = self._tree({"clean.md": "all good here.\n", "dirty.md": f"a dash {EM} here.\n"})
        out = io.StringIO()
        rc = ct.corpus_mode(paths, stdout=out)
        self.assertEqual(rc, 1)
        self.assertIn("dirty.md", out.getvalue())

    def test_clean_sweep_exits_0(self):
        paths = self._tree({"a.md": "plain prose.\n", "b.md": "more plain prose.\n"})
        rc = ct.corpus_mode(paths, stdout=io.StringIO())
        self.assertEqual(rc, 0)

    def test_empty_list_is_refused(self):
        rc = ct.corpus_mode([], stdout=io.StringIO(), stderr=io.StringIO())
        self.assertNotEqual(rc, 0)


class TextMode(unittest.TestCase):
    def _run(self, message_text):
        stdin, stderr = io.StringIO(message_text), io.StringIO()
        rc = ct.text_mode(["/tmp/project"], stdin=stdin, stderr=stderr)
        return rc, stderr.getvalue()

    def test_dirty_message_exits_2_and_names_the_string(self):
        rc, err = self._run(f"the work is done {EM} the board is clean")
        self.assertEqual(rc, 2)
        self.assertIn(EM, err)

    def test_clean_message_exits_0(self):
        rc, _err = self._run("the work is done, the board is clean.")
        self.assertEqual(rc, 0)


def _scratch_root():
    d = tempfile.mkdtemp()
    os.mkdir(os.path.join(d, ".claude"))
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


class TextModeSubprocess(unittest.TestCase):
    def test_passing_and_failing_leave_scratch_tree_untouched(self):
        root = _scratch_root()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root]))
        before = _tree_snapshot(root)
        clean = _run_text(root, "the work is done, the board is clean.")
        self.assertEqual(clean.returncode, 0)
        dirty = _run_text(root, f"the work is done {EM} the board is clean")
        self.assertEqual(dirty.returncode, 2)
        self.assertEqual(_tree_snapshot(root), before)

    def test_defaults_root_to_cwd(self):
        root = _scratch_root()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root]))
        result = subprocess.run(
            [sys.executable, _SCRIPT, "--text"],
            input="the work is done, the board is clean.",
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_crash_exits_neither_0_nor_2_nor_corpus_modes_1(self):
        # Invalid UTF-8 on stdin makes stdin.read() raise. A crash must never read as
        # a pass or a break, and it must not collide with corpus mode's exit 1.
        root = _scratch_root()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root]))
        result = subprocess.run(
            [sys.executable, _SCRIPT, "--text", root],
            input=b"\xff\xfe not valid utf-8",
            capture_output=True,
        )
        self.assertEqual(result.returncode, 3)


class HookVersusTextParity(unittest.TestCase):
    def _run_hook(self, root, message):
        path = _transcript(message)
        self.addCleanup(os.unlink, path)
        payload = json.dumps({"transcript_path": path, "stop_hook_active": False})
        return subprocess.run(
            [sys.executable, _SCRIPT, root],
            input=payload,
            capture_output=True,
            text=True,
        )

    def test_same_verdict_both_modes(self):
        for message in (
            "the work is done, the board is clean.",
            f"the work is done {EM} the board is clean",
        ):
            root = _scratch_root()
            self.addCleanup(lambda r=root: subprocess.run(["rm", "-rf", r]))
            hook_result = self._run_hook(root, message)
            text_result = _run_text(root, message)
            self.assertEqual(hook_result.returncode, text_result.returncode)
            self.assertEqual(hook_result.stderr, text_result.stderr)


if __name__ == "__main__":
    unittest.main()
