#!/usr/bin/env python3
"""Tests for fleet/settings.json, the fleet settings (shyrosa#97, #99).

Every machine's ~/.claude/settings.json is a link to this file, so a key that
drifts here drifts everywhere. These pin the keys the grill agreed on and keep
any one machine's home folder out of the file.
"""
import json
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(_HERE, "settings.json")


def load():
    with open(PATH) as f:
        return json.load(f)


class FleetSettings(unittest.TestCase):
    def test_compaction_is_off_both_ways(self):
        s = load()
        self.assertIs(s["autoCompactEnabled"], False)
        self.assertIs(s["idleCompaction"], False)

    def test_auto_memory_is_off_both_ways(self):
        s = load()
        self.assertIs(s["autoMemoryEnabled"], False)
        self.assertEqual(s["env"]["CLAUDE_CODE_DISABLE_AUTO_MEMORY"], "1")

    @unittest.skipUnless(os.path.exists(os.path.join(_HERE, "..", "export", "private-terms.txt")),
                         "the model choice stays in the private repo")
    def test_model_is_the_opus_alias_with_no_window_size(self):
        self.assertEqual(load()["model"], "opus")

    def test_ask_user_question_is_denied(self):
        self.assertIn("AskUserQuestion", load()["permissions"]["deny"])

    def test_both_write_guards_are_hooked(self):
        commands = [h["command"]
                    for entry in load()["hooks"]["PreToolUse"]
                    for h in entry["hooks"]]
        for script in ("check-writing-for-agents.py", "check-handoff-write.py"):
            self.assertTrue(any(script in c for c in commands), script)

    def test_preferences_are_briefed_at_session_start(self):
        hooks = [hook
                 for entry in load()["hooks"]["SessionStart"]
                 for hook in entry["hooks"]]
        self.assertIn({"type": "command",
                       "command": "python3 ~/.shyrosa/scripts/preferences.py --brief"}, hooks)

    def test_python_install_preference_guard_is_hooked_on_bash(self):
        commands = [h["command"]
                    for entry in load()["hooks"]["PreToolUse"]
                    if entry.get("matcher") == "Bash"
                    for h in entry["hooks"] if h.get("type") == "command"]
        self.assertIn("python3 ~/.shyrosa/scripts/check-preferences.py", commands)

    def test_no_machine_path(self):
        with open(PATH) as f:
            text = f.read()
        self.assertNotIn("/Users/", text)
        self.assertNotIn("/home/", text)

    def test_status_line_runs_from_home(self):
        self.assertTrue(load()["statusLine"]["command"].startswith("python3 ~/"))


if __name__ == "__main__":
    unittest.main()
