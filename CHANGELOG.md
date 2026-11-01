# Changelog

## v0.1.1, 2026-11-01

- Codex workers get the same prose guard as Claude Code: a Codex hook blocks an edit to a skill,
  `AGENTS.md`, `CLAUDE.md` or the rulebook until the writing skill is invoked in that turn.
- Agent instructions that Codex workers wrote earlier are rewritten for clarity. No rule changed.
- Choose Claude Code's tools with an optional setup wizard and user and machine
  preferences. Each session starts with the preferences in effect, reports missing
  tools and a changed or deleted fleet model when the checkout has one committed,
  and refuses Python package installs that conflict with a preference when the
  preferred tool is available. `wire.sh` points new installs at the wizard.
- Public exports leave out personal preference files and the fleet's model choice.
- Reboot restore reports Codex panes it skips and leaves live Codex and pi sessions
  alone.
- Messages between agents name their sender, including worker launch prompts,
  handoffs and reboot resumes. `tmux-orchestrator` refuses unsigned text sent into
  an agent pane; `send-raw` still lets a command be staged for the manager to submit.
- Codex workers and reviewers run at high effort in the projects named for Codex.
  Directors stay on Claude Code, and Codex workers stop and ask their director when
  a question touches shared work.
- The README recommends a sandboxed environment and explains why.
- The README explains the `## MANDATUM` section, its commands and `CONFIRM` lines.
- The board has a new look, a light/dark toggle, and separates work waiting on the
  manager from the rest of the desk. It still generates if its styling fails to load.
- The `teach` skill now asks for a light/dark toggle on every lesson page.

## v0.1.0, 2026-10-26

The first public release ships the rulebook and vocabulary, the skills that take
work from a grill through specs and tickets to workers and review, and the Foreman
that hands full sessions to fresh ones. It includes the message and style checks,
the project board, fleet settings and status line, tmux tools and reboot restore.
`wire.sh` links the setup into Claude Code and Codex. A guarded export keeps private
details out of the public copy.
