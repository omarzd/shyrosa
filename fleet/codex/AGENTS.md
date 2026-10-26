# The fleet, for codex

You are an agent in the manager's fleet. The project you are in has its own `AGENTS.md` or
`CLAUDE.md`; read it first. It points at the fleet rulebook, `~/.shyrosa/WORKFLOW-RULEBOOK.md`,
which binds you, and the vocab beside it, `~/.shyrosa/WORKFLOW-VOCAB.md`.

The rulebook is written for Claude Code. In codex:

- A skill the docs write as `/name` is invoked as `$name`.
- `EnterWorktree`, `ExitWorktree` and the `Skill` and `Agent` tools do not exist. A worker is
  started inside its worktree with `-C` and writes only under it.

Until the weekly reset on 2026-10-29, codex runs in every project. After it, codex runs only in a
project listed under *Projects named for codex* in shyrosa's `docs/agents/fleet-references.md`; in
any other folder, stop and say so before reading anything.
