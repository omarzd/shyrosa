#!/usr/bin/env python3
"""Exercise the guard's stdin/exit-code interface with synthetic transcripts only."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("check-writing-for-agents.py")


def message(role, content, **fields):
    return {"type": role, "message": {"content": content}, **fields}


def skill_call(call_id="skill-1", skill="writing-for-agents", name="Skill"):
    return message("assistant", [
        {"type": "tool_use", "id": call_id, "name": name, "input": {"skill": skill}}
    ])


def skill_result(call_id="skill-1", **fields):
    return message("user", [
        {"type": "tool_result", "tool_use_id": call_id,
         "content": "Synthetic skill result", **fields}
    ])


class WritingForAgentsGuard(unittest.TestCase):
    def run_payload(self, payload):
        return subprocess.run(
            [sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True,
        )

    def run_guard(self, entries, path="CLAUDE.md", tool="Edit"):
        with tempfile.TemporaryDirectory() as scratch:
            transcript = Path(scratch) / "synthetic.jsonl"
            transcript.write_text(
                "".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8"
            )
            return self.run_payload(json.dumps({
                "tool_name": tool,
                "tool_input": {"file_path": str(Path(scratch) / path)},
                "transcript_path": str(transcript),
            }))

    def test_failed_skill_call_blocks_guarded_edit(self):
        result = self.run_guard([
            message("user", "Edit the instructions"),
            skill_call(), skill_result(is_error=True),
        ])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("writing-for-agents", result.stderr)

    def test_successful_skill_result_allows_edit_and_write(self):
        for fields in ({}, {"is_error": False}):
            for tool in ("Edit", "Write"):
                with self.subTest(fields=fields, tool=tool):
                    result = self.run_guard([
                        message("user", "Edit the instructions"),
                        skill_call(), skill_result(**fields),
                    ], tool=tool)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_unfinished_call_blocks(self):
        result = self.run_guard([message("user", "Edit instructions"), skill_call()])
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_result_must_match_a_writing_for_agents_skill_call(self):
        for entries in (
            [skill_result()],
            [skill_call(), skill_result("different-id")],
            [skill_call(skill="tdd"), skill_result()],
            [skill_call(name="Bash"), skill_result()],
            [skill_result(), skill_call()],
            [message("user", skill_call()["message"]["content"], isMeta=True), skill_result()],
            [skill_call(), message("assistant", skill_result()["message"]["content"])],
        ):
            with self.subTest(entries=entries):
                result = self.run_guard([message("user", "Edit instructions"), *entries])
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_success_of_another_call_does_not_mask_failed_skill(self):
        result = self.run_guard([
            message("user", "Edit instructions"), skill_call(),
            skill_call("other-id", skill="tdd"), skill_result(is_error=True),
            skill_result("other-id"),
        ])
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_successful_retry_allows_edit(self):
        result = self.run_guard([
            message("user", "Edit instructions"), skill_call(), skill_result(is_error=True),
            skill_call("retry-id"), skill_result("retry-id"),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_later_failed_call_does_not_revoke_current_turn_success(self):
        result = self.run_guard([
            message("user", "Edit instructions"), skill_call(), skill_result(),
            skill_call("retry-id"), skill_result("retry-id", is_error=True),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_new_user_turn_clears_success_and_pending_calls(self):
        for content in ("Now edit again", [{"type": "text", "text": "Now edit again"}]):
            for results in ([], [skill_result()]):
                with self.subTest(content=content, results=results):
                    result = self.run_guard([
                        message("user", "Edit instructions"), skill_call(), *results,
                        message("user", content), skill_result(),
                    ])
                    self.assertEqual(result.returncode, 2, result.stderr)

    def test_meta_and_empty_messages_preserve_current_turn(self):
        for entry in (
            message("user", "Synthetic metadata", isMeta=True),
            message("user", "   "), message("user", []),
        ):
            with self.subTest(entry=entry):
                result = self.run_guard([
                    message("user", "Edit instructions"), skill_call(), entry, skill_result(),
                ])
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_typed_command_allows_its_own_turn(self):
        for command in ("writing-for-agents", "/writing-for-agents"):
            text = f"<command-name>{command}</command-name>"
            for content in (text, [{"type": "text", "text": text}]):
                with self.subTest(content=content):
                    result = self.run_guard([message("user", content)])
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_typed_command_expires_on_next_real_user_message(self):
        result = self.run_guard([
            message("user", "<command-name>/writing-for-agents</command-name>"),
            message("user", "Edit again"),
        ])
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_mentions_and_metadata_are_not_invocations(self):
        for entry in (
            message("assistant", '<command-name>/writing-for-agents</command-name>'),
            message("assistant", 'Example: "skill": "writing-for-agents"'),
            message("user", '<command-name>/writing-for-agents</command-name>', isMeta=True),
            message("user", 'Use the skill named "writing-for-agents"'),
            message("user", 'Example: "skill": "writing-for-agents"'),
            message("user", [{"type": "tool_result", "tool_use_id": "other-id",
                              "content": '<command-name>/writing-for-agents</command-name>'}]),
        ):
            with self.subTest(entry=entry):
                result = self.run_guard([message("user", "Edit instructions"), entry])
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_existing_guarded_file_scope(self):
        for path in (
            "CLAUDE.md", "AGENTS.md", "WORKFLOW-RULEBOOK.md", "WORKFLOW-VOCAB.md",
            "example/SKILL.md", ".claude/skills/example/reference.md",
            "overlay/example/reference.md", "docs/agents/example.md",
        ):
            with self.subTest(path=path):
                result = self.run_guard([message("user", "Edit instructions")], path=path)
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_working_records_and_other_tools_stay_exempt(self):
        for path in ("overlay/log-ruling/LEDGER.md", "GRILL-QUEUE.md", "STUDIO-QUEUE.md",
                     "GRILL-LOG.md", ".claude/handoffs/example.md", "scripts/example.py",
                     "docs/other/example.md"):
            with self.subTest(path=path):
                result = self.run_guard([], path=path)
                self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_guard([], tool="Read")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unreadable_transcript_and_invalid_payload_fail_open(self):
        with tempfile.TemporaryDirectory() as scratch:
            missing = Path(scratch) / "absent.jsonl"
            for payload in ("not json", json.dumps({
                "tool_name": "Edit", "tool_input": {"file_path": "CLAUDE.md"},
                "transcript_path": str(missing),
            })):
                with self.subTest(payload=payload):
                    result = self.run_payload(payload)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
