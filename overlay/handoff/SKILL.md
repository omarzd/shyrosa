---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save it to `.claude/handoffs/` in the current workspace, creating that folder if it is missing. Keep handoffs committed in the repo's history.

**Name the file for both ends:** `<writer>-to-<reader>-handoff.md`, numbering every end that has a
number. For example, `matt-flow-12-to-13-handoff.md`, `wayfinder-readability-07-to-matt-flow-10-handoff.md`.
A worker relief on one ticket names the ticket once (`t14-03-restructure-handoff.md`). The ticket
is both ends. A non-relief handoff that needs uniqueness dates the writer's end.

Include a "suggested skills" section in the document, naming which skills the next agent should call the Skill tool for.

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.

**If the handoff you were sent is missing or unreadable**, the work behind it is still recoverable. [`REBUILDING.md`](REBUILDING.md) has the two routes back.
