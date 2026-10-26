#!/usr/bin/env python3
"""Tests for statusline-context.py.

The module name has a hyphen, so it can't be imported by name; load it from
its path. The module guards its render behind __main__, so importing it here
runs no I/O — only the pure helpers are exercised.
"""
import importlib.util
import os
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "statusline_context", os.path.join(_HERE, "statusline-context.py")
)
sl = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sl)


class MostRecentEffortEvent(unittest.TestCase):
    def test_none_when_no_event(self):
        self.assertIsNone(sl.most_recent_effort_event("nothing here"))

    def test_single_ultracode(self):
        text = 'Set effort level to ultracode (this session only): xhigh + dynamic workflow orchestration'
        self.assertEqual(sl.most_recent_effort_event(text), "ultracode")

    def test_single_xhigh(self):
        text = 'Set effort level to xhigh (saved as your default for new sessions): Deeper reasoning'
        self.assertEqual(sl.most_recent_effort_event(text), "xhigh")

    def test_newest_wins_ultracode_then_xhigh(self):
        # Chronological order in the transcript: ultracode first, then xhigh.
        text = (
            'Set effort level to ultracode (this session only): xhigh + dynamic workflow orchestration\n'
            'later line\n'
            'Set effort level to xhigh (saved as your default for new sessions): Deeper reasoning\n'
        )
        self.assertEqual(sl.most_recent_effort_event(text), "xhigh")

    def test_newest_wins_xhigh_then_ultracode(self):
        text = (
            'Set effort level to xhigh (saved as your default for new sessions): Deeper reasoning\n'
            'Set effort level to ultracode (this session only): xhigh + dynamic workflow orchestration\n'
        )
        self.assertEqual(sl.most_recent_effort_event(text), "ultracode")


class ResolveEffortName(unittest.TestCase):
    def test_non_xhigh_passes_through(self):
        self.assertEqual(
            sl.resolve_effort_name({"effort": {"level": "high"}}, "", ""), "high"
        )

    def test_missing_effort_is_none(self):
        self.assertIsNone(sl.resolve_effort_name({}, "", ""))

    def test_xhigh_with_no_signal_stays_xhigh(self):
        self.assertEqual(
            sl.resolve_effort_name({"effort": {"level": "xhigh"}}, "", ""), "xhigh"
        )

    def test_mid_run_ultracode_from_transcript(self):
        tail = 'Set effort level to ultracode (this session only): xhigh + dynamic workflow orchestration'
        self.assertEqual(
            sl.resolve_effort_name({"effort": {"level": "xhigh"}}, tail, ""), "ultracode"
        )

    def test_mid_run_downgrade_to_xhigh_beats_launch(self):
        # Launched ultracode, then typed /effort xhigh. Transcript event wins.
        tail = (
            'Set effort level to ultracode (this session only): xhigh + dynamic workflow orchestration\n'
            'Set effort level to xhigh (saved as your default for new sessions): Deeper reasoning\n'
        )
        parent = "claude --effort ultracode"
        self.assertEqual(
            sl.resolve_effort_name({"effort": {"level": "xhigh"}}, tail, parent), "xhigh"
        )

    def test_launch_ultracode_when_no_transcript_event(self):
        parent = "claude --effort ultracode --model fable"
        self.assertEqual(
            sl.resolve_effort_name({"effort": {"level": "xhigh"}}, "", parent),
            "ultracode",
        )

    def test_launch_ultracode_equals_form(self):
        parent = "claude --effort=ultracode"
        self.assertEqual(
            sl.resolve_effort_name({"effort": {"level": "xhigh"}}, "", parent),
            "ultracode",
        )

    def test_plain_xhigh_launch_not_promoted(self):
        parent = "claude --effort xhigh"
        self.assertEqual(
            sl.resolve_effort_name({"effort": {"level": "xhigh"}}, "", parent), "xhigh"
        )

    def test_payload_marker_future_proof(self):
        # Launch-set: no transcript event, so the marker settles it.
        payload = {"effort": {"level": "xhigh", "ultracode": True}}
        self.assertEqual(sl.resolve_effort_name(payload, "", ""), "ultracode")

    def test_newest_transcript_event_beats_stale_marker(self):
        # A newer mid-run /effort xhigh must win over a marker (newest-wins).
        payload = {"effort": {"level": "xhigh", "ultracode": True}}
        tail = 'Set effort level to xhigh (saved as your default for new sessions): Deeper reasoning'
        self.assertEqual(sl.resolve_effort_name(payload, tail, ""), "xhigh")


class ResolveProject(unittest.TestCase):
    def test_prefers_payload_repo_name(self):
        payload = {"workspace": {"repo": {"name": "shyrosa"}}}
        self.assertEqual(sl.resolve_project(payload, "/anything/.git"), "shyrosa")

    def test_derives_from_common_dir_in_worktree(self):
        # git --path-format=absolute --git-common-dir from a worktree points at
        # the main checkout's .git; the project is its parent's basename.
        self.assertEqual(
            sl.resolve_project({}, "/Users/x/swMac1/shyrosa/.git"), "shyrosa"
        )

    def test_none_when_nothing(self):
        self.assertIsNone(sl.resolve_project({}, ""))


class MatchWindowByTty(unittest.TestCase):
    PANES = (
        "/dev/ttys005 claude-worker-1\n"
        "/dev/ttys031 matt-flow\n"
        "/dev/ttys002 Tom-Delalande-Director\n"
    )

    def test_matches_suffix(self):
        self.assertEqual(sl.match_window_by_tty("ttys031", self.PANES), "matt-flow")

    def test_no_match(self):
        self.assertIsNone(sl.match_window_by_tty("ttys099", self.PANES))

    def test_empty_tty(self):
        self.assertIsNone(sl.match_window_by_tty("??", self.PANES))

    def test_window_name_with_spaces(self):
        panes = "/dev/ttys002 Tom Delalande Director\n"
        self.assertEqual(
            sl.match_window_by_tty("ttys002", panes), "Tom Delalande Director"
        )


class ReadTail(unittest.TestCase):
    def test_reads_last_bytes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write("old line\n" * 100)
            f.write("FINAL MARKER\n")
            path = f.name
        try:
            tail = sl.read_tail(path, max_bytes=64)
            self.assertIn("FINAL MARKER", tail)
            self.assertLessEqual(len(tail.encode()), 64)
        finally:
            os.unlink(path)

    def test_missing_file_is_empty(self):
        self.assertEqual(sl.read_tail("/no/such/file"), "")


class BuildSegments(unittest.TestCase):
    """Deterministic assembly: no tmux in env, project from payload repo name."""

    PAYLOAD = {
        "effort": {"level": "medium"},
        "model": {"display_name": "Fable 5"},
        "workspace": {"repo": {"name": "shyrosa"}},
        "cwd": "/no/such/dir",
    }

    def _plain(self, segments):
        import re as _re
        return [_re.sub(r"\033\[[0-9;]*m", "", s) for s in segments]

    def test_no_tmux_drops_window_no_empty_segment(self):
        # Env without TMUX/TMUX_PANE: the window segment must be absent, and no
        # segment may be empty (an empty one would render a dangling separator).
        segs = self._plain(sl.build_segments(self.PAYLOAD, {}))
        self.assertNotIn("", segs)
        self.assertIn("medium", segs)
        self.assertIn("shyrosa", segs)
        # No window name leaked in without tmux.
        self.assertNotIn("claude-worker-1", segs)

    def test_effort_and_project_present(self):
        segs = self._plain(sl.build_segments(self.PAYLOAD, {}))
        self.assertIn("Fable 5", segs)
        self.assertIn("shyrosa", segs)


if __name__ == "__main__":
    unittest.main()
