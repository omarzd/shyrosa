# shyrosa

shyrosa is how I run a team of Claude Code agents: one director per project, one worker per
ticket, a rulebook they all follow, and checks that hold them to it.

## The problem

One Claude Code session is a good pair programmer. Five at once are a mess. They forget what was
decided yesterday, ask the same question twice, build before the plan is clear, merge their own
work, and write me long reports that bury the one thing I have to decide. The agents were never
the slow part of the work. My attention was.

## How it works

Every project gets a **director**: a long-running Claude Code session that owns the project's
tickets and is the only agent that talks to me. A piece of work moves through fixed stages:

```
  me ──► grill ──► spec ──► tickets ──► workers ──► gate ──► merge
          │                               │           │
          └── questions, one at a time    │           └── director checks the work
                                          └── one tmux pane and one git worktree per ticket
```

- **Grill.** Before anything is built, the director questions me one question at a time until
  nothing is left open. Each answer is written down where it belongs.
- **Spec and tickets.** The answers become a spec on the issue tracker. The spec is cut into
  tickets, thin slices that each work end to end and each say which tickets must finish first.
- **Workers.** Each ticket gets a fresh worker in its own tmux pane and its own git worktree.
  A worker builds, tests, and stops. It never merges.
- **Gate.** The director reads the worker's diff, runs the tests, and merges only what passes.
  Anything that leaves the machine, a push or a deletion, waits for my word.
- **Foreman.** A separate agent watches how full each session's context is and replaces a
  session with a fresh one, with a written handoff, before it runs out.

**The rulebook** is one file every agent in every project reads at the start of a session. When
I settle how something should work, the ruling goes into the rulebook, so no agent asks it again.
A vocabulary file beside it defines the words the agents use with each other and with me.

**The checks** are hooks and scripts that run before a message reaches me. Every message must end
with a short section holding the exact line I would type next, so I decide by copying one line. A
style check rejects padded, machine-sounding prose. A board file shows every project's tickets on
one page.

## What is here now

Only this README and the license. The rulebook, the skills, the checks and the scripts that wire
them into Claude Code follow over the coming weeks. They are exported from my private working
copy, which also holds my notes on real projects, and a guard stops any export that would carry
a private detail.

## Credit

shyrosa is built on [Matt Pocock's skills](https://github.com/mattpocock/skills), MIT licensed.
The grill, the spec and the ticket skills start from his. My changed copies keep his license
notice. Install his skills from his repo, not from here.

## License

MIT. See [LICENSE](LICENSE).
