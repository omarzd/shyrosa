#!/usr/bin/env python3
"""The tells detector — a mechanical slop grep beside the mandatum check (ticket 21).

One copy for the fleet, the same house pattern as check-mandatum.py: pure functions
behind a `__main__` guard, no I/O at import. It judges no soul — only the mechanical
tells the output style bans by character or word. Four classes:

  - an em or en dash;
  - a hyphen set off as a dash (` - ` between words);
  - a curly quote;
  - a word from the style's worst-vocabulary list (pattern 7: delve, crucial,
    testament, tapestry and kin).

Three modes. Message mode rides the Stop hook beside the mandatum check: it reads the
turn's last assistant message from the transcript and, on any finding, exits 2 so the
bounce lands loudly in the writing agent's own pane. The agent repairs and resends;
it never rewrites silently. Every bounce names the offending string and its fix, never
only the crime (WORKFLOW-RULEBOOK.md, the g03 repair-first rule).

Text mode judges a draft instead of a turn: the message rides stdin as plain text, the
project root rides argv (unused here, kept for the same convention as the mandatum
check), and the verdict is the one message mode would give on the same text. No
transcript read. Any exit besides 0 or 2 means the check itself broke.

Corpus mode scans an explicitly named file list, never a bare glob, and reports findings
per file. Records stay dashed, so an empty list is refused rather than glob-expanded. A
zero-findings run exits clean: that is how every sweep ticket proves itself done.

Code is exempt. The style keeps code, commands, and paths byte-for-byte exact, so a
fenced ``` block and an inline `code` span are stripped before prose is scanned.

The set amends only at the manager's word, in one commit: any string WORKFLOW-RULEBOOK.md
quotes verbatim from this checker, a heading, a line shape, a bounce phrase, changes in
the same commit as the line here it quotes, so rulebook and check never drift apart.
"""
import json
import re
import sys
import time

EM_DASH = "—"
EN_DASH = "–"
CURLY = {"‘": "'", "’": "'", "“": '"', "”": '"'}

# Pattern 7 of the style, plus the common inflections of each, as one fixed set. The
# match is a whole word, case-insensitive; the detector flags the occurrence and leaves
# the judgment of whether a plainer word fits to the agent who resends.
VOCAB = (
    "additionally", "crucial", "crucially",
    "delve", "delves", "delved", "delving",
    "enduring", "enhance", "enhances", "enhanced", "enhancing", "enhancement",
    "foster", "fosters", "fostered", "fostering",
    "garner", "garners", "garnered", "garnering",
    "interplay", "intricate", "intricately",
    "landscape", "landscapes",
    "pivotal", "showcase", "showcases", "showcased", "showcasing",
    "tapestry", "tapestries",
    "testament", "underscore", "underscores", "underscored", "underscoring",
    "vibrant", "vibrantly",
)
_VOCAB_RE = re.compile(r"\b(" + "|".join(VOCAB) + r")\b", re.I)
_HYPHEN_DASH_RE = re.compile(r"\w - \w")  # a hyphen with a space each side, used as a dash
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def line_tells(line):
    """Every tell on one prose line, each message naming the string and its fix."""
    out = []
    if EM_DASH in line:
        out.append(f"an em dash '{EM_DASH}': end the sentence with a full stop, or join the clauses with a comma")
    if EN_DASH in line:
        out.append(f"an en dash '{EN_DASH}': end the sentence with a full stop, or join the clauses with a comma")
    if _HYPHEN_DASH_RE.search(line):
        out.append("a hyphen set off as a dash ' - ': end the sentence or use a comma, never a spaced hyphen")
    for ch, straight in CURLY.items():
        if ch in line:
            out.append(f"a curly quote '{ch}': use the straight quote '{straight}'")
    for m in _VOCAB_RE.finditer(line):
        out.append(f"'{m.group(0)}': pattern 7 vocabulary, use a plain word")
    return out


def scan(text):
    """Findings across a whole text as (line_number, message) pairs, code excluded.

    Fenced ``` blocks are skipped whole and inline `code` spans are dropped per line, so
    the line numbers stay true to the file for corpus mode to point at.
    """
    findings = []
    in_fence = False
    for i, raw in enumerate(text.splitlines(), 1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        prose = _INLINE_CODE_RE.sub("", raw)
        for msg in line_tells(prose):
            findings.append((i, msg))
    return findings


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


def render_findings(findings, stderr):
    """Findings to a verdict: exit code plus the printed bounce, shared by every mode
    that judges one message (message mode and text mode alike)."""
    if not findings:
        return 0
    print("TELLS check — this message carries mechanical slop the style bans (unslop.md). Repair each and resend:", file=stderr)
    for _line, msg in findings:
        print(f"  - {msg}", file=stderr)
    return 2


def message_mode(argv, stdin=sys.stdin, stderr=sys.stderr):
    """Ride the Stop hook: scan the turn's last message, exit 2 on any finding.

    argv[0] is the project path, carried for the same convention as the mandatum check;
    the detector needs no project facts, so it is accepted and ignored.
    """
    payload = json.load(stdin)
    if payload.get("stop_hook_active"):
        return 0  # this turn was already sent back once; never loop the writer
    transcript_path = payload.get("transcript_path", "")
    message = last_assistant_text(transcript_path)
    if not message.strip():
        # The Stop hook can fire before the final message is flushed to the transcript;
        # one re-read after a beat closes that race, the same guard the mandatum check keeps.
        time.sleep(0.5)
        message = last_assistant_text(transcript_path)
    return render_findings(scan(message), stderr)


def text_mode(argv, stdin=sys.stdin, stderr=sys.stderr):
    """--text: judge a draft straight off stdin, no transcript read.

    argv[0] is the project root, the same convention as the mandatum check's --text;
    this detector needs no project facts, so it is accepted and ignored.
    """
    message = stdin.read()
    return render_findings(scan(message), stderr)


def corpus_mode(paths, stdout=sys.stdout, stderr=sys.stderr):
    """Scan a named file list and report findings per file; zero findings exits clean."""
    if not paths:
        print("TELLS corpus mode takes an explicit file list; a bare glob is refused, so records stay dashed.", file=stderr)
        return 2
    total = 0
    for path in paths:
        try:
            with open(path, errors="replace") as fh:
                text = fh.read()
        except OSError as e:
            print(f"{path}: cannot read ({e})", file=stderr)
            total += 1
            continue
        findings = scan(text)
        if findings:
            print(f"{path}: {len(findings)} finding(s)", file=stdout)
            for line_no, msg in findings:
                print(f"  {line_no}: {msg}", file=stdout)
            total += len(findings)
    if total == 0:
        print("zero findings", file=stdout)
        return 0
    return 1


def main():
    args = sys.argv[1:]
    if args and args[0] == "--corpus":
        return corpus_mode(args[1:])
    if args and args[0] == "--text":
        try:
            return text_mode(args[1:])
        except Exception as e:
            # A crash must never read as a pass or a break, and exit 1 is corpus
            # mode's "findings present" — so a broken check gets its own code,
            # distinct from both.
            print(f"TELLS check --text crashed: {e}", file=sys.stderr)
            return 3
    return message_mode(args)


if __name__ == "__main__":
    sys.exit(main())
