#!/usr/bin/env python3
"""PreToolUse guard: agent-read prose is edited only under /writing-for-agents.

Ruled in sitting g02 (2026-08-16), GRILL-QUEUE §1.

Hooked in ~/.claude/settings.json on Edit|Write, machine-wide. Blocks (exit 2) when
the target is a guarded file and no typed /writing-for-agents command or successful
Skill result exists in the current turn — after the last real user message.
In-context text from an earlier turn is not invocation; that is the exact failure
this guard exists to stop.

Guarded: skill prose (any SKILL.md, and .md files under a skills dir or overlay/),
CLAUDE.md, AGENTS.md, docs/agents/*.md, WORKFLOW-RULEBOOK.md, WORKFLOW-VOCAB.md.
Working records (queues, ledger, grill log, handoffs) are not guarded.

Fails open: a broken guard must not freeze every edit on the machine.
"""

import json
import re
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
    # Any .md riding inside a skill folder: ~/.claude/skills/<skill>/… or overlay/<skill>/…
    if "/.claude/skills/" in path or "/overlay/" in path:
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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if payload.get("tool_name") not in ("Edit", "Write"):
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
