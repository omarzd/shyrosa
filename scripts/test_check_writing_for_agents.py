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


def codex_event(turn_id, event_type, **fields):
    return {"type": "event_msg", "payload": {
        "type": event_type, "turn_id": turn_id, **fields,
    }}


def codex_skill(turn_id="current", name="writing-for-agents", role="user"):
    return {"type": "response_item", "payload": {
        "type": "message", "role": role,
        "content": [{"type": "input_text", "text": f"<skill>\n<name>{name}</name>\n</skill>"}],
        "internal_chat_message_metadata_passthrough": {"turn_id": turn_id},
    }}


def codex_read(turn_id="current", command=None, **fields):
    return codex_event(turn_id, "item_completed", item={
        "type": "CommandExecution", "id": "synthetic-read",
        "command": ["/bin/zsh", "-lc", command or "cat ~/.codex/skills/writing-for-agents/SKILL.md"],
        "status": "completed", "exit_code": 0, **fields,
    })


class CodexWritingForAgentsGuard(unittest.TestCase):
    def run_guard(self, entries=(), patch=None, **fields):
        with tempfile.TemporaryDirectory() as scratch:
            transcript = Path(scratch) / "synthetic.jsonl"
            transcript.write_text("".join(json.dumps(e) + "\n" for e in entries))
            payload = {
                "tool_name": "apply_patch", "cwd": scratch, "turn_id": "current",
                "transcript_path": str(transcript),
                "tool_input": {"command": patch or (
                    "*** Begin Patch\n*** Update File: AGENTS.md\n@@\n-old\n+new\n*** End Patch"
                )}, **fields,
            }
            return subprocess.run(
                [sys.executable, str(SCRIPT)], input=json.dumps(payload),
                capture_output=True, text=True,
            )

    def test_guarded_patch_without_invocation_is_blocked_with_codex_repair(self):
        result = self.run_guard([codex_event("current", "task_started")])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("$writing-for-agents", result.stderr)
        self.assertIn("AGENTS.md", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_current_turn_skill_item_allows_edit(self):
        result = self.run_guard([codex_event("current", "task_started"), codex_skill()])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_completed_current_turn_shell_read_allows_edit(self):
        for command in (
            "cat ~/.codex/skills/writing-for-agents/SKILL.md",
            "sed -n '1,240p' '/synthetic path/writing-for-agents/SKILL.md'",
            "cat AGENTS.md; cat upstream/writing-for-agents/SKILL.md",
            "echo inspecting\ncat upstream/writing-for-agents/SKILL.md",
            "true && cat upstream/writing-for-agents/SKILL.md",
            "exec cat upstream/writing-for-agents/SKILL.md",
            "nl -ba upstream/writing-for-agents/SKILL.md",
        ):
            with self.subTest(command=command):
                result = self.run_guard([
                    codex_event("current", "task_started"), codex_read(command=command),
                ])
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_conditional_and_compound_shell_reads_need_a_separate_direct_read(self):
        path = "upstream/writing-for-agents/SKILL.md"
        for command in (
            f"test -f {path} || cat {path}",
            f"if true; then cat {path}; fi",
            f"case x in x) cat {path};; esac",
            f"for x in one; do cat {path}; done",
            f"while false; do cat {path}; done",
            f"until true; do cat {path}; done",
            f"read_skill() {{ cat {path}; }}; read_skill",
        ):
            with self.subTest(command=command):
                result = self.run_guard([
                    codex_event("current", "task_started"), codex_read(command=command),
                ])
                self.assertEqual(result.returncode, 2, result.stderr)
                retry = self.run_guard([
                    codex_event("current", "task_started"), codex_read(command=command), codex_read(),
                ])
                self.assertEqual(retry.returncode, 0, retry.stderr)

    def test_earlier_turn_invocations_do_not_count(self):
        for invocation in (codex_skill("earlier"), codex_read("earlier")):
            with self.subTest(invocation=invocation):
                result = self.run_guard([
                    codex_event("earlier", "task_started"), invocation,
                    codex_event("current", "task_started"),
                ])
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_mentions_wrong_skills_and_incomplete_or_failed_reads_do_not_count(self):
        for item in (
            codex_skill(name="tdd"), codex_skill(role="assistant"),
            codex_read(status="in_progress", exit_code=None),
            codex_read(status="failed", exit_code=1), codex_read(exit_code=1),
            codex_read(command="echo cat ~/.codex/skills/writing-for-agents/SKILL.md"),
            codex_read(command="cat ~/.codex/skills/tdd/SKILL.md"),
        ):
            with self.subTest(item=item):
                result = self.run_guard([codex_event("current", "task_started"), item])
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_all_patch_headers_and_moves_guard_either_path(self):
        for header in (
            "*** Add File: docs/agents/new.md\n+new",
            "*** Delete File: AGENTS.md",
            "*** Update File: old.txt\n*** Move to: AGENTS.md\n@@\n-old\n+new",
            "*** Update File: AGENTS.md\n*** Move to: old.txt\n@@\n-old\n+new",
            "*** Update File: /synthetic/CLAUDE.md\n@@\n-old\n+new",
            "*** Update File: nested/../AGENTS.md\n@@\n-old\n+new",
        ):
            with self.subTest(header=header):
                result = self.run_guard([codex_event("current", "task_started")],
                                        patch=f"*** Begin Patch\n{header}\n*** End Patch")
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_paths_resolve_against_hook_cwd(self):
        result = self.run_guard([codex_event("current", "task_started")],
                                cwd="/synthetic/overlay/example",
                                patch="*** Begin Patch\n*** Add File: reference.md\n+new\n*** End Patch")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("/synthetic/overlay/example/reference.md", result.stderr)

    def test_indented_file_headers_still_guard_prose(self):
        for header in (
            "  *** Add File: docs/agents/space name.md\n+new",
            "\t*** Update File: AGENTS.md\n@@\n-old\n+new",
            "  *** Delete File: AGENTS.md",
        ):
            with self.subTest(header=header):
                result = self.run_guard([codex_event("current", "task_started")],
                                        patch=f"*** Begin Patch\n{header}\n*** End Patch")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(header.split(": ", 1)[1].split("\n", 1)[0], result.stderr)

    def test_indented_move_destination_still_guards_prose(self):
        result = self.run_guard([codex_event("current", "task_started")], patch=(
            "*** Begin Patch\n*** Update File: ordinary.txt\n"
            "  *** Move to: directory with spaces/AGENTS.md\n@@\n-old\n+new\n*** End Patch"
        ))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("directory with spaces/AGENTS.md", result.stderr)

    def test_trailing_header_whitespace_preserves_spaces_inside_paths(self):
        for header in (
            "*** Add File: docs/agents/space name.md \t\n+new",
            "*** Update File: directory with spaces/AGENTS.md \t\n@@\n-old\n+new",
            "*** Delete File: directory with spaces/AGENTS.md \t",
            "*** Update File: ordinary.txt\n*** Move to: directory with spaces/AGENTS.md \t\n@@\n-old\n+new",
        ):
            with self.subTest(header=header):
                result = self.run_guard([codex_event("current", "task_started")],
                                        patch=f"*** Begin Patch\n{header}\n*** End Patch")
                self.assertEqual(result.returncode, 2, result.stderr)
                expected = "space name.md" if "space name.md" in header else "directory with spaces/AGENTS.md"
                self.assertIn(expected, result.stderr)

    def test_boundary_whitespace_still_guards_prose(self):
        for begin, end in (
            ("*** Begin Patch \t", "*** End Patch"),
            ("*** Begin Patch", "  *** End Patch \t"),
            ("  *** Begin Patch \t", "\t*** End Patch \t"),
        ):
            with self.subTest(begin=begin, end=end):
                result = self.run_guard([codex_event("current", "task_started")], patch=(
                    f"{begin}\n*** Add File: AGENTS.md\n+new\n{end}"
                ))
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_heredoc_wrappers_still_guard_prose(self):
        for opener in ("<<EOF", "<<'EOF'"):
            with self.subTest(opener=opener):
                result = self.run_guard([codex_event("current", "task_started")], patch=(
                    f"{opener}\n*** Begin Patch\n*** Add File: AGENTS.md\n+new\n*** End Patch\nEOF"
                ))
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_unicode_line_separator_in_content_cannot_invent_a_header(self):
        result = self.run_guard([codex_event("current", "task_started")], patch=(
            "*** Begin Patch\n*** Add File: ordinary.txt\n"
            "+content\u2028*** Update File: AGENTS.md\n*** End Patch"
        ))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_update_context_cannot_invent_a_file_header(self):
        for context in (
            " *** Add File: AGENTS.md", " *** Update File: AGENTS.md",
            " *** Delete File: AGENTS.md", " *** Move to: AGENTS.md",
        ):
            for marker in ("@@\n", ""):
                if not marker and context == " *** Move to: AGENTS.md":
                    continue  # before the first hunk this is move metadata
                with self.subTest(context=context, marker=marker):
                    result = self.run_guard([codex_event("current", "task_started")], patch=(
                        "*** Begin Patch\n*** Update File: ordinary.txt\n"
                        f"{marker}{context}\n-old\n+new\n*** End Patch"
                    ))
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_codex_skill_reference_prose_is_guarded(self):
        result = self.run_guard([codex_event("current", "task_started")], patch=(
            "*** Begin Patch\n*** Add File: .codex/skills/example/reference.md\n+new\n*** End Patch"
        ))
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_mixed_patch_blocks_but_ordinary_code_and_records_pass(self):
        for path, expected in (
            ("scripts/example.py", 0), ("GRILL-QUEUE.md", 0), ("STUDIO-QUEUE.md", 0),
            ("GRILL-LOG.md", 0), ("overlay/log-ruling/LEDGER.md", 0),
            (".claude/handoffs/example.md", 0), ("AGENTS.md", 2),
        ):
            with self.subTest(path=path):
                patch = ("*** Begin Patch\n*** Add File: ordinary.txt\n+new\n"
                         f"*** Add File: {path}\n+new\n*** End Patch")
                result = self.run_guard([codex_event("current", "task_started")], patch=patch)
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_codex_malformed_input_and_unrecognised_transcript_fail_open(self):
        for fields in (
            {"turn_id": None}, {"tool_input": {}}, {"tool_input": {"command": "bad patch"}},
            {"cwd": None}, {"transcript_path": "/synthetic/missing.jsonl"},
        ):
            with self.subTest(fields=fields):
                result = self.run_guard([codex_event("current", "task_started")], **fields)
                self.assertEqual(result.returncode, 0, result.stderr)
        for entries in ([], [{"type": "future_rollout_format"}],
                        [{"type": "future_rollout_format", "payload": {"turn_id": "current"}}], [None],
                        [codex_event("current", "task_started"), None]):
            with self.subTest(entries=entries):
                result = self.run_guard(entries)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
