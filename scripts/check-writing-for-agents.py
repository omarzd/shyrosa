#!/usr/bin/env python3
"""PreToolUse guard: agent-read prose is edited only under /writing-for-agents.

Ruled in sitting g02 (2026-08-16), GRILL-QUEUE §1.

Hooked in ~/.claude/settings.json on Edit|Write and ~/.codex/hooks.json on apply_patch.
Blocks (exit 2) when a guarded file is edited without the writing skill this turn.
Claude counts a typed /writing-for-agents command or successful Skill result after
the last real user message. Codex counts a <skill> item or completed shell read
of writing-for-agents/SKILL.md attributed to the hook input's turn_id.
In-context text from an earlier turn is not invocation; that is the exact failure
this guard exists to stop.

Guarded: skill prose (any SKILL.md, and .md files under a skills dir or overlay/),
CLAUDE.md, AGENTS.md, docs/agents/*.md, WORKFLOW-RULEBOOK.md, WORKFLOW-VOCAB.md.
Working records (queues, ledger, grill log, handoffs) are not guarded.

Fails open: a broken guard must not freeze every edit on the machine.
"""

import json
import os
import re
import shlex
import sys


GUARDED_BASENAMES = {"CLAUDE.md", "AGENTS.md", "WORKFLOW-RULEBOOK.md", "WORKFLOW-VOCAB.md"}

# The manager's typed command. Agent invocations need a matching successful result.
INVOKE_RE = re.compile(
    r"<command-name>/?writing-for-agents</command-name>"
)


def is_guarded(path: str) -> bool:
    if not path.endswith(".md"):
        return False
    parts = path.split("/")
    base = parts[-1]
    if base == "LEDGER.md":
        return False  # the ledger is a record, not agent instructions — it lives in overlay/ but stays open
    if base in GUARDED_BASENAMES:
        return True
    if base == "SKILL.md":
        return True
    # Skill prose under either harness's skills folder, or the overlay source.
    if "/.claude/skills/" in path or "/.codex/skills/" in path or "/overlay/" in path:
        return True
    if len(parts) >= 3 and parts[-3] == "docs" and parts[-2] == "agents":
        return True
    return False


def is_real_user_line(entry: dict) -> bool:
    """A user turn that carries text — a prompt or a typed command, not a tool result."""
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(
            isinstance(block, dict) and block.get("type") == "text" and block.get("text", "").strip()
            for block in content
        )
    return False


def invoked_this_turn(transcript_path: str) -> bool:
    invoked = False
    pending = set()
    with open(transcript_path, encoding="utf-8") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = (entry.get("message") or {}).get("content")
            if is_real_user_line(entry):
                pending.clear()
                texts = [content] if isinstance(content, str) else [
                    block.get("text", "") for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                # A typed command is itself the user turn that authorizes the edit.
                invoked = any(INVOKE_RE.search(text) for text in texts)
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if (entry.get("type") == "assistant"
                        and block.get("type") == "tool_use"
                        and block.get("name") == "Skill"
                        and (block.get("input") or {}).get("skill") == "writing-for-agents"
                        and block.get("id")):
                    pending.add(block["id"])
                elif (entry.get("type") == "user"
                        and block.get("type") == "tool_result"
                        and block.get("tool_use_id") in pending):
                    pending.remove(block["tool_use_id"])
                    if not block.get("is_error", False):
                        invoked = True
    return invoked


def codex_patch_paths(command: str, cwd: str) -> list[str]:
    """Codex apply_patch headers name both sides of a move, relative to cwd."""
    lines = command.strip().split("\n")
    if lines[0].strip() in {"<<EOF", "<<'EOF'"} and lines[-1].strip() == "EOF":
        lines = lines[1:-1]
    if lines[0].strip() != "*** Begin Patch" or lines[-1].strip() != "*** End Patch":
        raise ValueError("unrecognised patch")
    paths = []
    in_update_hunk = False
    awaiting_update_hunk = False
    for line in lines:
        header = line.strip()
        if awaiting_update_hunk and not header.startswith("*** Move to: "):
            in_update_hunk = True
            awaiting_update_hunk = False
        if in_update_hunk and line.startswith((" ", "+", "-")):
            continue  # hunk content keeps its prefix, even when it spells a header
        match = re.fullmatch(r"\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)", header)
        if match:
            in_update_hunk = False
            if not header.startswith("*** Move to: "):
                awaiting_update_hunk = header.startswith("*** Update File: ")
            paths.append(os.path.normpath(os.path.join(cwd, match[1])))
    if not paths or not os.path.isabs(cwd):
        raise ValueError("missing patch paths or cwd")
    return paths


def reads_writing_skill(command: list[str]) -> bool:
    """Recognise direct readers; compound shell forms need a separate direct read.

    The g41/#155 ruling accepts plain readers, exec readers and ;/&&/newline
    chains, not readers after || or inside shell control flow. This is a
    guardrail, not a general shell interpreter.
    """
    lexer = shlex.shlex(command[-1], posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace_split = True
    lexer.whitespace = " \t\r"
    segments = []
    words = []
    direct = True
    for token in lexer:
        if token in {"{", "}"} or all(char in "()" for char in token):
            return False  # function, subshell or case pattern
        if token and all(char in ";&|\n" for char in token):
            segments.append((direct, words))
            words = []
            direct = token.replace("\n", "") in {"", ";", "&&"}
        else:
            words.append(token)
    segments.append((direct, words))
    control = {"if", "then", "elif", "else", "fi", "case", "esac",
               "for", "while", "until", "do", "done", "function"}
    if any(words and words[0] in control for _, words in segments):
        return False
    readers = {"cat", "sed", "head", "tail", "nl", "less", "more", "bat"}
    for direct, words in segments:
        if words and words[0] == "exec":
            words = words[1:]
        if (direct and words and os.path.basename(words[0]) in readers
                and any(word.endswith("/writing-for-agents/SKILL.md") for word in words[1:])):
            return True
    return False


def codex_invoked_this_turn(transcript_path: str, turn_id: str) -> bool:
    """Read the 0.164 rollout shape; unknown turn attribution fails open."""
    if not turn_id:
        raise ValueError("missing turn id")
    seen_turn = False
    invoked = False
    with open(transcript_path, encoding="utf-8") as fh:
        for line in fh:
            entry = json.loads(line)
            payload = entry.get("payload", {})
            item_turn = payload.get("turn_id") or payload.get(
                "internal_chat_message_metadata_passthrough", {}
            ).get("turn_id")
            if item_turn != turn_id:
                continue
            if entry.get("type") not in {"turn_context", "response_item", "event_msg"}:
                continue
            seen_turn = True
            if (entry.get("type") == "response_item" and payload.get("type") == "message"
                    and payload.get("role") == "user"):
                invoked |= any(
                    re.search(r"<skill>\s*<name>writing-for-agents</name>", block.get("text", ""))
                    is not None for block in payload.get("content", [])
                    if block.get("type") == "input_text"
                )
            elif entry.get("type") == "event_msg" and payload.get("type") == "item_completed":
                item = payload.get("item", {})
                if (item.get("type") == "CommandExecution" and item.get("status") == "completed"
                        and item.get("exit_code") == 0):
                    invoked |= reads_writing_skill(item["command"])
    if not seen_turn:
        raise ValueError("unrecognised turn")
    return invoked


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool = payload.get("tool_name")
        if tool == "apply_patch":
            paths = codex_patch_paths(payload["tool_input"]["command"], payload["cwd"])
            guarded = [path for path in paths if is_guarded(path)]
            if not guarded or codex_invoked_this_turn(payload["transcript_path"], payload["turn_id"]):
                return 0
            print(
                f"Guarded file: {', '.join(guarded)} is agent-read prose. "
                "Invoke $writing-for-agents now, in this turn, then retry the edit; "
                "an invocation from an earlier turn does not count.", file=sys.stderr,
            )
            return 2
        if tool not in ("Edit", "Write"):
            return 0
        path = (payload.get("tool_input") or {}).get("file_path", "")
        if not is_guarded(path):
            return 0
        if invoked_this_turn(payload.get("transcript_path", "")):
            return 0
    except Exception:
        return 0  # fail open — a broken guard must not freeze the machine
    print(
        f"Guarded file: {path} is agent-read prose. Invoke /writing-for-agents "
        "(the Skill tool) successfully now, in this turn, then retry the edit — an invocation "
        "from an earlier turn does not count, and in-context text is not invocation.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
