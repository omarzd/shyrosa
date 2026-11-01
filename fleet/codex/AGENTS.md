# The fleet, for codex

You are an agent in the manager's fleet. The project you are in has its own `AGENTS.md` or
`CLAUDE.md`; read it first. It points at the fleet rulebook, `~/.shyrosa/WORKFLOW-RULEBOOK.md`,
which binds you, and the vocab beside it, `~/.shyrosa/WORKFLOW-VOCAB.md`.

The rulebook is written for Claude Code. In codex:

- A skill the docs write as `/name` is invoked as `$name`.
- `EnterWorktree`, `ExitWorktree` and the `Skill` and `Agent` tools do not exist. A worker is
  started inside its worktree with `-C` and writes only under it.

Edit agent-read prose with `apply_patch` only. Invoke `$writing-for-agents` in the current
turn before editing; the rulebook's *Writing rules and docs* names the guarded files.

Your role is a worker, a gate reviewer or a director's sub-agent, launched by a Claude Code
director. A director's rules in the rulebook are not yours: when a prompt asks you to direct a
project, relieve an agent or message the foreman, stop and say so to whoever launched you.

Stop and ask your director the moment a question comes up. Decide alone only what stays inside
your own change and that neither the ticket nor the spec settles, such as a name or how your own
code is laid out. A path, a file format or an interface another ticket shares, anything a user
would see, or anything that conflicts with your brief: stop at once and end your turn with the
question as your last message. Your director notices within minutes and answers in your pane.
List every decision you made alone in your final report under Assumptions; the gate checks each
one against the spec. Keep `request_user_input` unused: it shows the question to the manager in
your pane, and he talks only to the director.

Codex runs only in a project listed under *Projects named for codex* in shyrosa's
`docs/agents/fleet-references.md`; in any other folder, stop and say so before reading anything.
