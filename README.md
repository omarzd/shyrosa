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

## What is here

The rulebook and the vocabulary beside it, my skills in `overlay/`, Matt Pocock's skills in
`upstream/`, the fleet settings and status line in `fleet/`, the scripts the checks and the board
run, and `wire.sh`, which links it all into Claude Code. All of it is exported from my private
working copy, which also holds my notes on real projects, and a guard stops any export that would
carry a private detail.

## Install

You need Claude Code, git, Python 3 and tmux, and the command line for wherever your project's
issues live, logged in:

- GitHub Issues: [`gh`](https://cli.github.com), logged in with `gh auth login`. The setup skill
  creates the triage labels with it, and without it that step fails with `gh: command not found`.
- GitLab Issues: [`glab`](https://gitlab.com/gitlab-org/cli), logged in with `glab auth login`.
- Local markdown, issues as files under `.scratch/` in the project: nothing more.
- Another tracker, such as Jira or Linear: whatever its own tools need. The setup skill asks you
  to describe how you use it and writes that down for the other skills to follow.

```
git clone https://github.com/omarzd/shyrosa.git
cd shyrosa
./wire.sh --link-settings
```

`wire.sh` links the skills into `~/.claude/skills`, links the status-line script and the Unslop
style into `~/.claude`, and makes `~/.shyrosa` a link to this checkout, which the hooks and skills
use to find the rulebook and the scripts. A skill of mine wins over one of Matt's with the same
name. Run it again after every pull. It is safe to run any number of times.

`--link-settings` is the one-time step. It points `~/.claude/settings.json` at
`fleet/settings.json`, which is my whole Claude Code setup: the model and effort I use, the
permissions, the hooks that run the checks, and auto-memory off. Read it before you link it. If
your settings file is a real file, `wire.sh` renames it to `settings.json.pre-fleet` and never
deletes it. Later runs keep the link without the flag.

Then start a Claude Code session in one of your own projects:

```
cd ~/my-project
claude
```

## Starting in a project

In a new project I run `/setup-matt-pocock-skills` once. It asks where the project's issues live,
then writes `docs/agents/` and an `## Agent skills` section in `CLAUDE.md`, which the other
skills read.

After that, a piece of work goes through four commands:

- `/grill-with-docs` asks me one question at a time until the plan has no open question, and
  writes the project's glossary and decision records as the answers settle.
- `/to-spec` turns that conversation into a spec and publishes it on the issue tracker with the
  `spec` label.
- `/to-tickets` cuts the spec into tickets, each naming the tickets that must finish first, and
  publishes them with the `ready-for-agent` label.
- `/implement` builds a ticket test-first, reviews the work and commits it to the current branch.
  It never merges.

When I don't know which command comes next, I run `/ask-matt` and ask it.

## Credit

shyrosa is built on [Matt Pocock's skills](https://github.com/mattpocock/skills), MIT licensed.
The grill, the spec and the ticket skills start from his. My changed copies keep his license
notice. His own skills ship unchanged in `upstream/`, and
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) carries his license for both.

## License

MIT. See [LICENSE](LICENSE).
