# ShyRosa

ShyRosa is an agentic AI workflow with its own checks and rules. Use it to analyze any problem, design the solution, and implement it through multiple agents. ShyRosa is built on Matt Pocock’s skills, though extended with many quality of life improvements. Refer to [Matt Pocock’s page](https://www.aihero.dev/) if this is unclear to you. 

## The problem

Claude Code and Codex are the most famous coding harnesses. They host many models (LLMs) and provide an interface between you and the coding agent. They work well for ‘small’ projects and horribly for large ones. While the floor and ceiling for what small and large mean in the physical world keep rising with every new release, humans’ expectations and ambitions adapt quickly and rise even faster; hence, *small* is in inverted commas. No matter how big it gets, it will always be perceived as small. 

The problem is when these coding agents perform horribly. They disobey direct orders. They make things up. They don’t inquire enough, but rather assume things. Every agentic AI workflow out there, including ShyRosa, aims to solve this problem.

## What do I need to have to start using ShyRosa 

I strongly recommend Claude Code, as does Matt Pocock. But you can also use it with Codex since I’ve tested it on Codex. I’ve also tested having the director (defined below) be a Claude or GPT agent while workers spawned by the director be on a different harness, namely Oh-My-Pi with OpenRouter. It worked but it was too costly and unsatisfactory. I haven’t tested it on other harness setups, though it should theoretically work.

This README assumes you’re using Claude Code.

> [!WARNING]
> **Disclaimer**: This is the last human-written line. From here on, it’s AI slop. Well in fact, this entire project has been built using ShyRosa itself as the framework with Claude Fable 5 and 5.1 for 35% of the content and Opus 5.5 for 40% of the content.

Besides Claude Code, you need four things on your computer:

- **A terminal.** The window where you type commands. On a Mac the built-in Terminal app works.
- **tmux.** A free program that holds many terminal windows inside one. ShyRosa runs every agent
  in its own tmux window, so you can switch to any agent and watch it work, and agents can pass
  messages to each other. On a Mac, install it with `brew install tmux` (Homebrew, from
  [brew.sh](https://brew.sh)).
- **git.** It keeps the history of every change in your project, so nothing an agent does is
  lost or impossible to undo. Your project needs to be a folder git keeps track of.
- **Python 3.** ShyRosa's checks are small Python programs. Macs ask to install it the first
  time you run `python3`.

What the author uses, if you want a starting point:

- **macOS:** [WezTerm](https://wezterm.org) with tmux, set up from
  [Tom Delalande's setup](https://github.com/tom-delalande/setup). The author's own version is
  more customized and will be shared later.
- **Windows:** [wmux](https://github.com/openwong2kim/wmux), one app that is both the terminal and
  the tmux-style windows. It also adds its own tools to Claude Code when you install it.
- **Debian, Ubuntu and similar Linux:** tmux in any terminal. WezTerm runs there too.

You also need a place for your project's to-do list. ShyRosa calls each item on it a ticket.
It can be GitHub Issues, GitLab Issues, plain files inside your project, or a tracker you
already use, such as Jira or Linear. *Install*, below, says what each one needs.

## How it works

You talk to one agent per project, the **director**. It is a Claude Code session that stays open,
owns the project's to-do list, and is the only agent that talks to you. It starts other agents,
called **workers**, and tells them what to build. A piece of work moves through fixed steps:

```
  you ──► grill ──► spec ──► tickets ──► workers ──► check ──► merge
           │                               │           │
           └── questions, one at a time    │           └── the director checks the work
                                           └── one worker per ticket, each on its own copy
```

- **Grill.** Before anything is built, the director asks you questions, one at a time, until
  nothing about the plan is left open. It writes down every answer.
- **Spec and tickets.** Your answers become a spec, a short document saying what will be built
  and why. The director cuts the spec into tickets: small pieces of work that each do something
  you can see, and each say which tickets must be finished first.
- **Workers.** Each ticket gets a fresh worker in its own tmux window, working on its own copy
  of your project so two workers never get in each other's way. A worker builds, tests its
  work, and stops.
- **Check.** The director reads what the worker changed and runs the tests. Only work that
  passes goes into your project. That last step is the merge, and no worker ever does it for
  itself.

Anything that leaves your computer, such as uploading your code or deleting something online,
waits until you say yes.

**The Foreman** is a helper agent that runs alongside every project, not a step in the list
above. An agent can only hold so much of a conversation in mind at once. When one gets close to
full, the Foreman starts a fresh agent and hands it a written summary of where the work stands,
so nothing is lost and you don't have to explain it all again.

**The rulebook** is one file every agent reads when it starts. When you settle how something
should work, your answer goes into the rulebook, so no agent asks you the same thing twice. A
vocabulary file next to it defines the words the agents use with each other and with you.

**The checks** run before a message reaches you. When an agent needs something from you, its
message ends with a short section holding the exact line you would type next, so you decide by
copying one line. Another check rejects padded, robotic-sounding writing. A board file shows the
to-do list of every project on one page.

## What is here

- The rulebook and the vocabulary file.
- ShyRosa's own skills, in `overlay/`. A skill is a set of written instructions an agent
  follows for one kind of job.
- Matt Pocock's skills, unchanged, in `upstream/`.
- The recommended Claude Code settings and status line, in `fleet/`.
- The small programs behind the checks and the board, in `scripts/`.
- `wire.sh`, which connects all of it to Claude Code.

All of it is copied from the author's private working copy, which also holds notes on real
projects. A check stops any copy that would carry a private detail.

## Sandbox

Agents can type commands into any tmux window, and workers can run commands without asking you
first.

A sandboxed environment is highly recommended: its own machine, a VM, or at least a separate OS
account that has no access to your personal files or credentials.

## Answering the director

When the director needs your decision, its message ends with a section headed exactly
`## Mandatum? Ik Willen!`. *Mandatum* is Latin for a command handed down. Everything the
director needs from you is in that section, and nothing else is. When it needs nothing, the
message has no such section.

The section holds two kinds of line:

- **A command**, such as `/to-tickets g14`. Copy it as it is and type it in the same window.
- **A `CONFIRM` line**, which asks you to approve one step. Answer by typing its label back, such
  as `CONFIRM 1`. Numbered lines stand alone, so you can approve any of them. Lettered lines,
  such as `CONFIRM 1a` and `CONFIRM 1b`, are a choice: pick one.

```text
---
## Mandatum? Ik Willen!
/to-tickets g14
CONFIRM 1: publish the export
```

The full rules are in the vocabulary file's [`## MANDATUM` entry](WORKFLOW-VOCAB.md#the-board)
and the rulebook's [Writing to the manager](WORKFLOW-RULEBOOK.md#writing-to-the-manager).

## Install

First, set up the command line for wherever your to-do list lives, and log in:

- GitHub Issues: install [`gh`](https://cli.github.com) and run `gh auth login`. Without it, the
  setup step that creates the to-do list's labels fails with `gh: command not found`.
- GitLab Issues: install [`glab`](https://gitlab.com/gitlab-org/cli) and run `glab auth login`.
- Plain files inside your project, under `.scratch/`: nothing to install.
- Another tracker, such as Jira or Linear: whatever its own tools need. The setup step asks you
  how you use it and writes that down for the agents.

Then download ShyRosa and connect it to Claude Code. In a terminal:

```
git clone https://github.com/omarzd/shyrosa.git
cd shyrosa
./wire.sh --link-settings
```

`wire.sh` makes ShyRosa's skills available to Claude Code, adds the status line and the writing
style, and makes `~/.shyrosa` point at this folder, which is how the checks find the rulebook.
Where a ShyRosa skill and a Matt Pocock skill share a name, ShyRosa's is used. Run `./wire.sh`
again after every update. Running it twice does no harm.

`--link-settings` is needed only the first time. It replaces your Claude Code settings with
ShyRosa's recommended ones in `fleet/settings.json`: the effort level, which actions agents may
take without asking, the checks that run on every message, and Claude Code's automatic memory
switched off. Read that file before you run this. If you already have a settings file, `wire.sh`
keeps it as `~/.claude/settings.json.pre-fleet` and never deletes it.

Then open Claude Code in one of your own projects:

```
cd ~/my-project
claude
```

## Starting in a project

The first time in a project, run `/setup-matt-pocock-skills`. It asks where the project's to-do
list lives, and writes that down where the other skills will read it.

After that, each piece of work takes four commands:

- `/grill-with-docs` asks you one question at a time until the plan has no open question, and
  writes down the project's terms and decisions as you settle them.
- `/to-spec` turns that conversation into a spec and adds it to your to-do list, labelled `spec`.
- `/to-tickets` cuts the spec into tickets and adds them to your to-do list, labelled
  `ready-for-agent`.
- `/implement` builds one ticket, writing a test first, checks its own work and saves it. It
  never merges.

If you don't know which command comes next, run `/ask-matt` and ask it.

## Credit

ShyRosa is built on [Matt Pocock's skills](https://github.com/mattpocock/skills), MIT licensed.
The grill, the spec and the ticket skills start from his. ShyRosa's changed copies keep his
license notice. His own skills ship unchanged in `upstream/`, and
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) carries his license for both.

## License

MIT. See [LICENSE](LICENSE).
