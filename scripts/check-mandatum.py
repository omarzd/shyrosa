#!/usr/bin/env python3
"""The MANDATUM check — a grep riding the board's Stop hook (wayfinder ticket 09).

One copy for the fleet. The project root arrives as argv[1]; the project's facts —
the board's HTML path — come from `<root>/.claude/fleet.json` through fleet_config, so
the check itself carries no project paths.

Reads the turn's last assistant message from the session transcript. A message without
the `## Mandatum? Ik Willen!` heading passes untouched. A message with one is checked against
the three grep-able rules from tickets 03 and 04: the closed command set, the two line shapes,
and the colon separator. On a break it exits 2 so the breaks land loudly in the writing
agent's own pane — the agent rewrites and resends; it never rewrites or blocks silently.

`--text` judges a draft instead of a turn: the message rides stdin as plain text, the
project root rides argv, and the verdict is the one the Stop hook would give on the same
message. No transcript read, and the board flag is touched in neither direction, so a
board-line claim goes unjudged, same as the missing-flag case (WORKFLOW-RULEBOOK.md,
Writing to the manager). Any exit besides 0 or 2 means the check itself broke.

The set amends only at the manager's word, in one commit, and the guard reaches past
the command set: any string WORKFLOW-RULEBOOK.md quotes verbatim from this checker, a
heading, a line shape, a bounce phrase, changes in the same commit as the line here it
quotes, so rulebook and check never drift apart.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet_config  # noqa: E402

COMMANDS = ("/triage", "/grill-me", "/grill-with-docs", "/wayfinder", "/implement", "/to-spec", "/to-tickets", "/ask-matt", "/log-ruling", "/handoff")
WORDS = ("CONFIRM",)  # HOLD is his standing word, never a row a director writes
BLOCK_HEADING = "## Mandatum? Ik Willen!"  # his string, his casing (2026-08-27, superseding g14's Equilen); matched verbatim
HIS_HEADINGS = {BLOCK_HEADING, "## STUDIO ROUND"}


def load_config(root):
    """The project's facts, read at run time so importing the module does no I/O."""
    root, cfg = fleet_config.load(root)
    board_line = "Board updated: file://" + cfg["board_html"]
    flag_path = os.path.join(root, ".claude", "board-changed")
    return board_line, flag_path


def wrong_heading(message):
    """A bare, shortened, or old-dash heading, when the exact new one is absent.

    Fires only on a heading-shaped line, never on a prose mention like
    'the `## MANDATUM` section', so a rule quote is not mistaken for the heading.
    """
    return bool(re.search(r"^\s*#*\s*mandatum\b", message, re.M | re.I))


def prose_ask_bounces(message):
    """A message that asks for his word in prose instead of a section line (g03/g11)."""
    unquoted = re.sub(r"[`*_]", "", message)
    return bool(
        re.search(
            r"\bsay the word\b(?!\s+(?:section|heading|block|check|set|rule|phrase|name|line))",
            unquoted,
            re.I,
        )
    )


def last_assistant_text(transcript_path):
    text = None
    with open(transcript_path, errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                continue
            content = entry.get("message", {}).get("content", [])
            blocks = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            if blocks:
                text = "\n".join(blocks)
    return text or ""


def check(message, board_changed, board_line):
    breaks = []
    lines = message.splitlines()

    for l in lines:
        row = re.sub(r"^[-*]\s+", "", l.strip())
        if row.startswith("Board updated:") and row != board_line:
            breaks.append(f"'{row}' — the board line is locked verbatim: {board_line}")
    if board_line in (re.sub(r"^[-*]\s+", "", l.strip()) for l in lines) and board_changed is False:
        breaks.append("the message says Board updated, and the board did not change this turn — an unchanged board gets no line")

    heading_rows = [i for i, l in enumerate(lines) if l.startswith("## ")]
    for i in heading_rows:
        if lines[i].strip() not in HIS_HEADINGS:
            breaks.append(f"'{lines[i].strip()}' — his sections are the only ## headings in a message; write your own headings at a different weight")

    block_rows = [i for i, l in enumerate(lines) if l.strip() == BLOCK_HEADING]
    if not block_rows:
        return breaks
    block_at = block_rows[0]

    if any(l.startswith("#") for l in lines[block_at + 1:]):
        breaks.append("a heading follows the ## MANDATUM section — the section is last, with nothing after it")

    if not any(re.match(r"^-{3,}\s*$", l) for l in lines[:block_at]):
        breaks.append("the --- line is missing: put a line holding only --- above his first section, since the two zones split on it")

    asks = 0
    bad_rows = 0
    confirms = []
    for l in lines[block_at + 1:]:
        row = l.strip()
        if not row or row == board_line:
            continue
        row = re.sub(r"^[-*]\s+", "", row)
        # A markdown code-wrap is legal dress — the line inside is what he copies (g03).
        row = re.sub(r"^`(.+)`$", r"\1", row).strip()
        if row == board_line:
            continue
        first = row.split()[0]
        # A stray colon may still glue to the command; strip it to name the command
        # in the bounce, then bounce the colon itself below (his ruling, no colons
        # after commands).
        cmd = first[:-1] if first.endswith(":") else first
        if first == "HOLD":
            breaks.append("HOLD written as a row — it is his standing word, listed on the board, never offered")
        elif first.startswith("/"):
            asks += 1
            if cmd not in COMMANDS:
                breaks.append(f"'{cmd}' — not one of the closed commands: {', '.join(COMMANDS)} (WORKFLOW-RULEBOOK.md, Writing to the manager)")
            elif ":" in row:
                breaks.append(f"'{row}' — no colon on a command line: the line is the command as typed, <command> <args>, like /log-ruling g14")
            elif " — " in row or " – " in row:
                breaks.append(f"'{row}' — no separator on a command line: the line is the command as typed, <command> <args>")
            elif cmd == "/triage":
                if not re.match(r"^/triage \d+ ", row):
                    breaks.append(f"'{row}' — the /triage line carries a count: /triage <N> tickets waiting for a sitting")
            elif len(row.split()) < 2:
                breaks.append(f"'{row}' — a command line names the thing in its args: <command> <args>")
        elif first in WORDS:
            asks += 1
            confirms.append(row)
        else:
            bad_rows += 1
            breaks.append(f"'{row}' — not a legal line. Repair it and keep the section: a line opens with a closed command ({', '.join(COMMANDS)}) or with CONFIRM; formatting wrapped around the opener is what usually hides it")

    for row in confirms:
        numbered = re.match(r"^CONFIRM (\d+[a-z]?) (\S+): \S", row)
        plain = re.match(r"^CONFIRM (\S+): \S", row)
        if len(confirms) > 1:
            if not numbered:
                breaks.append(f"'{row}' — more than one CONFIRM in this message, so each is labelled: CONFIRM <n> <handle>: <the thing he is confirming>, and lines he must choose between share a number and take letters (1a, 1b)")
        elif not (numbered or plain):
            breaks.append(f"'{row}' — the CONFIRM line is CONFIRM <handle>: <the thing he is confirming>")
    if len(confirms) > 1:
        labels = [m.group(1) for m in (re.match(r"^CONFIRM (\d+[a-z]?) ", r) for r in confirms) if m]
        if len(set(labels)) != len(labels):
            breaks.append("two CONFIRM lines share a label — he answers by label, so each one is distinct")
        # A letter means pick one of these, so a number is either one standalone line or a
        # lettered group of two or more — never both shapes, and never a lone letter.
        groups = {}
        for label in labels:
            groups.setdefault(re.match(r"\d+", label).group(0), []).append(label)
        for num, group in groups.items():
            lettered = [x for x in group if x != num]
            if lettered and len(lettered) != len(group):
                breaks.append(f"CONFIRM {num} is written both bare and lettered — a number is one standalone line or a group of options, never both")
            elif len(lettered) == 1:
                breaks.append(f"'CONFIRM {lettered[0]}' is a lettered group of one — letters mean he picks one of several, so give it a sibling or drop the letter")

    if asks == 0:
        if bad_rows:
            breaks.append("no legal ask parsed — repair the lines above and keep the section; a section is dropped only when nothing truly waits on him")
        else:
            breaks.append("the section holds nothing that waits on him — when nothing does, there is no section; a lone board line stands by itself")
    return breaks


def judge_early(message, board_line=None):
    """A verdict reachable without board state at all: (exit_code, stderr_lines), or
    None when the message needs the section rules and so the flag. Split out so hook
    mode can skip its flag read on these paths exactly as it always has."""
    if BLOCK_HEADING not in message:
        if wrong_heading(message):
            lines = [
                f"MANDATUM check — the heading is '{BLOCK_HEADING}', exactly, his casing; a bare, shortened, or old-dash heading dodges the rules the heading carries. Restore the exact heading and resend."
            ]
            # Judge the rest as if the heading were right, so one resend fixes every
            # break at once rather than surfacing the next one a bounce later.
            swapped = re.sub(r"^\s*#*\s*mandatum\b.*$", BLOCK_HEADING, message, count=1, flags=re.M | re.I)
            others = check(swapped, None, board_line) if board_line else []
            if others:
                lines.append("  Fix these in the same resend:")
                lines += [f"  - {b}" for b in others]
            return 2, lines
        # A prose ask dodges every rule the section carries — the g03 escape: bounced
        # once, a director asked in prose instead. Backticks and emphasis come off
        # first, because rule-discussion quotes the phrase and one stray ` used to
        # defeat the noun list below — it bounced this rule's own grill twice (g11).
        if prose_ask_bounces(message):
            return 2, [
                f"MANDATUM check — this message asks for his word in prose. A wait belongs in the '{BLOCK_HEADING}' section, one legal line per wait; put it there and resend."
            ]
        if "Board updated:" not in message:
            return 0, []
    return None


def judge_rules(message, board_changed, board_line):
    """The verdict from the section rules, once a message has reached them."""
    breaks = check(message, board_changed, board_line)
    if not breaks:
        return 0, []
    lines = ["MANDATUM check — this message breaks the section's rules (WORKFLOW-RULEBOOK.md, Writing to the manager). Rewrite and resend:"]
    lines += [f"  - {b}" for b in breaks]
    return 2, lines


def judge(message, board_changed, board_line):
    """The verdict on one message: (exit_code, stderr_lines). Used where board state is
    already in hand (text mode always, hook mode once past judge_early)."""
    early = judge_early(message, board_line)
    if early is not None:
        return early
    return judge_rules(message, board_changed, board_line)


def text_mode(argv):
    """--text: judge a draft straight off stdin. No transcript read, no flag touch in
    either direction — the flag is written at Stop, and a draft-time read would hold
    last turn's state, so a board-line claim goes unjudged here, the same as the
    missing-flag case in hook mode."""
    root = argv[0] if argv else os.getcwd()
    board_line, _flag_path = load_config(root)
    message = sys.stdin.read()
    code, lines = judge(message, None, board_line)
    for l in lines:
        print(l, file=sys.stderr)
    return code


def main():
    args = sys.argv[1:]
    if args and args[0] == "--text":
        try:
            return text_mode(args[1:])
        except Exception as e:
            # A crash must never read as a pass or a break, and exit 1 is the tells
            # checker's corpus-mode "findings present" — so a broken check gets its
            # own code, distinct from both.
            print(f"MANDATUM check --text crashed: {e}", file=sys.stderr)
            return 3

    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return 0  # this turn was already sent back once; never loop the director
    root = args[0] if args else os.getcwd()
    board_line, flag_path = load_config(root)
    message = last_assistant_text(payload.get("transcript_path", ""))
    if BLOCK_HEADING not in message:
        # The Stop hook can fire before the turn's final message is flushed to the
        # transcript — this let a seven-break block through on 2026-08-09. One
        # re-read after a beat closes the race.
        time.sleep(0.5)
        message = last_assistant_text(payload.get("transcript_path", ""))

    early = judge_early(message, board_line)
    if early is not None:
        code, lines = early
        board_changed = None
    else:
        try:
            board_changed = open(flag_path).read().strip() == "1"
        except FileNotFoundError:
            board_changed = None  # no verdict from the generator; claims go unjudged rather than misjudged
        code, lines = judge_rules(message, board_changed, board_line)

    if code == 0:
        # The flag is sticky: the render raises it, and only this clears it — once a
        # passing message has actually delivered the board line (WORKFLOW-QUEUE §28).
        # A message without the line leaves the flag up; the pointer is owed until sent.
        if board_changed and board_line in message:
            with open(flag_path, "w") as fh:
                fh.write("0")
    for l in lines:
        print(l, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
