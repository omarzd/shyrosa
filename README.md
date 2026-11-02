# ShyRosa

ShyRosa is an agentic AI workflow with its own checks and rules. Use it to analyze any problem, design the solution, and implement it through multiple agents. It is built on
[Matt Pocock's skills](https://www.aihero.dev/), with many changes on top.

## The problem

Claude Code and Codex are the best-known coding harnesses. A harness hosts one or more AI
models and gives you a way to talk to the coding agent. They work well for *small* projects
and horribly for large ones. Every few months a new release handles projects that the last one
could not. But people immediately try something bigger. The bar for what counts as *small*
keeps rising, yet we will keep calling it small. 

The trouble starts when the agent disobeys a direct instruction, makes something up, or
assumes instead of asking. Every agentic AI workflow, ShyRosa included, tries to stop that
from happening.

## What do I need to start using ShyRosa?

The author recommends Claude Code, as does Matt Pocock. It also works with Codex. The author
has tested having the director (defined below) run as a Claude or GPT agent while workers run
on a different harness, Oh-My-Pi with OpenRouter. It worked but was too costly and the results
were not good enough. Other harness setups should work in theory but have not been tested.

This README assumes you are using Claude Code.

> [!WARNING]
> **Disclaimer**: This is the last human-written line. From here on, it's AI slop. Well in fact, this entire project has been built using ShyRosa itself as the framework with Claude Fable 5 and 5.1 for 35% of the content and Opus 5.5 for 40% of the content.

Besides Claude Code, you need four things on your computer:

- **A terminal.** This is the window where you type commands. On a Mac the built-in Terminal
  app works.
- **tmux.** A free program that lets you keep many terminal windows open inside one screen.
  ShyRosa gives every agent its own tmux window. You can switch between them to watch any
  agent work. Agents also use tmux to pass messages to each other. On a Mac, install it with
  `brew install tmux` (Homebrew, from [brew.sh](https://brew.sh)).
- **git.** A program that records every change anyone makes to your project. If an agent does
  something wrong, you can always go back. You need to set up git to track your project folder
  before you start.
- **Python 3.** ShyRosa's checks are small Python programs. On a Mac, the system asks you to
  install Python the first time you run `python3`.

What the author uses, if you want a starting point:

- **macOS:** [WezTerm](https://wezterm.org) with tmux, set up from
  [Tom Delalande's setup](https://github.com/tom-delalande/setup). The author's own version is
  more customized and will be shared later.
- **Windows:** [wmux](https://github.com/openwong2kim/wmux), one app that is both the terminal and
  the tmux-style windows. It also adds its own tools to Claude Code when you install it.
- **Debian, Ubuntu and similar Linux:** tmux in any terminal. WezTerm runs there too.

You also need somewhere to keep your project's to-do list. ShyRosa calls each item on the list
a "ticket". This can be GitHub Issues, GitLab Issues, local markdown files inside your project, or a
tracker you already use, such as Jira or Linear. The *Install* section below says what each
one needs.

## How it works

You talk to one agent per project. That agent is called the **director**. It is a Claude Code
session that stays open, owns the project's to-do list, and is the only agent that talks to
you. When there is work to do, the director starts other agents called **workers** and tells
them what to build. A piece of work moves through these steps:

```
  you ──► grill ──► spec ──► tickets ──► workers ──► check ──► merge
           │                               │           │
           └── questions, one at a time    │           └── the director checks the work
                                           └── one worker per ticket, each on its own copy
```

- **Grill.** Before anything is built, the director asks you questions one at a time until
  there is nothing unclear about the plan. It writes down every answer.
- **Spec and tickets.** Your answers become a spec, which is a short document saying what will
  be built and why. The director splits the spec into tickets, each describing one piece of
  work you can see the result of. Each ticket also says which other tickets need to finish
  first.
- **Workers.** Each ticket gets its own worker in a separate tmux window, working on its own
  copy of your project. Because each worker has its own copy, two workers never interfere with
  each other. A worker builds, tests its work, and stops.
- **Check.** The director reads what the worker changed and runs the tests. Only work that
  passes gets added to your project. That last step, the merge, is something no worker ever
  does on its own.

Anything that would leave your computer, such as uploading your code or deleting something
online, waits until you say yes.

**The Foreman** is a helper agent that runs alongside every project. It is not a step in the
list above. Every agent has a limited amount of conversation it can hold in memory at once.
The Foreman watches that limit. Before an agent runs out of room, the Foreman moves what
matters into a fresh agent that picks up where the old one left off. This works better than
Claude Code's built-in compacting, which just summarizes the conversation and loses detail.

**The rulebook** is one file every agent reads when it starts. When you settle how something
should work, your answer goes into the rulebook. After that, no agent asks you the same thing
twice. A
vocabulary file next to it defines the words the agents use with each other and with you.

**The checks** run before a message reaches you. When an agent needs something from you, its
message ends with a short section that holds the exact line you would type next. You decide by
copying one line. A separate check rejects padded, robotic-sounding writing. A board file
shows the to-do list of every project on one page.

## What is here

- The rulebook and the vocabulary file.
- ShyRosa's own skills, in `overlay/`. A "skill" is a set of written instructions that tells
  an agent how to do one kind of job.
- Matt Pocock's skills, unchanged, in `upstream/`.
- The recommended Claude Code settings and status line, in `fleet/`.
- The small programs behind the checks and the board, in `scripts/`.
- `wire.sh`, which connects all of the above to Claude Code.

## Sandbox

Agents can type commands into any tmux window, and workers can run commands without asking you
first. This means they have real access to whatever is on the machine.

Because of this, running ShyRosa in a sandboxed environment is a good idea. That could be a
separate machine, a virtual machine, or at the very least a separate user account on your
computer that cannot reach your personal files or passwords.

## Answering the director

When the director needs you to do something or approve something, its message ends with a
section headed exactly `## Mandatum? Ik Willen!`. The word *Mandatum* is Latin for a command
handed down. Everything the director needs from you is in that section, nothing else. When
it needs nothing, the message has no such section.

The section holds two kinds of line:

- **A command**, such as `/to-tickets g14`. Copy it exactly as written and type it in the same
  window.
- **A `CONFIRM` line**, which asks you to approve one step. You answer by typing the label
  back, such as `CONFIRM 1`. Numbered lines are independent, so you can approve any of them
  in any order. Lettered lines, such as `CONFIRM 1a` and `CONFIRM 1b`, are a choice between
  options: pick one.

```text
---
## Mandatum? Ik Willen!
/to-tickets g14
CONFIRM 1: publish the export
```

The full rules are in the vocabulary file's [`## MANDATUM` entry](WORKFLOW-VOCAB.md#the-board)
and the rulebook's [Writing to the manager](WORKFLOW-RULEBOOK.md#writing-to-the-manager).

## Install

First, set up the command-line tool for wherever your to-do list lives, and log in:

- GitHub Issues: install [`gh`](https://cli.github.com) and run `gh auth login`. Without this,
  the setup step that creates labels on your to-do list will fail with `gh: command not found`.
- GitLab Issues: install [`glab`](https://gitlab.com/gitlab-org/cli) and run `glab auth login`.
- Local markdown files inside your project, under `.scratch/`: nothing to install.
- Another tracker, such as Jira or Linear: whatever its own tools need. The setup step will ask
  you how you use it and write that down for the agents.

Then download ShyRosa and connect it to Claude Code. In a terminal, type:

```
git clone https://github.com/omarzd/shyrosa.git
cd shyrosa
./wire.sh --link-settings
```

`wire.sh` makes ShyRosa's skills available to Claude Code, adds the status line and the
writing style, and makes `~/.shyrosa` point at this folder so the checks can find the
rulebook. If a ShyRosa skill and a Matt Pocock skill share a name, Claude Code uses
ShyRosa's. Run `./wire.sh` again after every update. Running it twice does no
harm.

`--link-settings` is needed only the first time. It replaces your Claude Code settings file
with ShyRosa's recommended one at `fleet/settings.json`. That file sets the effort level,
which actions agents may take without asking, and the checks that run on every message. It
also turns off several Claude Code features ShyRosa replaces or does not need, such as
automatic memory, automatic compacting, the built-in skills, the pop-up question tool, plan
mode, and scheduled tasks. Every one of those features loads into memory when an agent starts,
before it has done any work. Turning them off means a fresh agent has more room left for your
project. Read that file before you run this. If you already have a settings file, `wire.sh`
saves it as `~/.claude/settings.json.pre-fleet` and never deletes it.

Then open Claude Code in one of your own projects:

```
cd ~/my-project
claude
```

## Starting in a project

The first time you use ShyRosa in a project, run `/setup-matt-pocock-skills`. It asks where
the project's to-do list lives and writes the answer down where the other skills will read it.

After that, each piece of work takes four commands:

- `/grill-with-docs` asks you one question at a time until nothing about the plan is unclear.
  It also writes down the project's terms and decisions as you settle them.
- `/to-spec` turns that conversation into a spec and adds it to your to-do list, labelled
  `spec`.
- `/to-tickets` splits the spec into tickets and adds them to your to-do list, labelled
  `ready-for-agent`.
- `/implement` builds one ticket. It writes a test first, checks its own work, and saves it.
  It never merges.

If you are not sure which command comes next, run `/ask-matt` and ask it.

## Credit

ShyRosa is built on [Matt Pocock's skills](https://github.com/mattpocock/skills), which are
MIT licensed. The grill, the spec, and the ticket skills all started as his. ShyRosa's changed
copies keep his license notice. His original skills ship unchanged in `upstream/`, and
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) carries his license for both.

## License

MIT. See [LICENSE](LICENSE).
