#!/usr/bin/env python3
"""PreToolUse guard: a handoff file is written only under /handoff.

Ruled in sitting g04 (2026-08-16), GRILL-QUEUE §2.

Sibling of check-writing-for-agents.py, hooked beside it on Edit|Write. Blocks
(exit 2) when the target sits in `.claude/handoffs/` and no /handoff invocation
exists in the current turn — after the last real user message. A rolling draft
maintained between turns is exactly the failure this guard exists to stop:
recovery already belongs to the transcript, and a draft is a cache of it that
decays. Relief is the foreman's; a filling agent says so to whoever watches it.

Exact-match on the skill name: `manage-handoffs` must not satisfy `handoff`.
Fails open: a broken guard must not freeze every edit on the machine.
"""

import json
import re
import sys


INVOKE_RE = re.compile(
    r"<command-name>/?handoff</command-name>"
    r"|\"skill\"\s*:\s*\"handoff\""
)


def is_real_user_line(entry: dict) -> bool:
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
    last_user = -1
    last_invoke = -1
    with open(transcript_path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if INVOKE_RE.search(line):
                last_invoke = i
            if '"type":"user"' in line or '"type": "user"' in line:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if is_real_user_line(entry):
                    last_user = i
    return last_invoke >= last_user and last_invoke != -1


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if payload.get("tool_name") not in ("Edit", "Write"):
            return 0
        path = (payload.get("tool_input") or {}).get("file_path", "")
        if "/.claude/handoffs/" not in path or not path.endswith(".md"):
            return 0
        if invoked_this_turn(payload.get("transcript_path", "")):
            return 0
    except Exception:
        return 0  # fail open — a broken guard must not freeze the machine
    print(
        f"Guarded path: {path} is a handoff file, written only under a current-turn "
        "/handoff invocation. A handoff is written once, under a /handoff typed by "
        "the manager or sent by your relief-holder at relief — a rolling draft is a decaying cache of the transcript, "
        "which already holds everything and survives everything. If your context is "
        "filling, say so to whoever watches you, and stop.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
