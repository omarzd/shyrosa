---
name: tmux-orchestrator
description: Coordinate multiple agents/processes across tmux panes. Use to list panes in the current tmux session, send a prompt to an agent (Pi, Claude Code, codex, or any CLI) in another pane, read a pane's output back, or when agents in panes need to communicate with each other. Replaces CMAX-style multi-agent workflows.
---

# tmux Orchestrator

Drive other processes (typically AI agents) running in sibling tmux panes:
discover panes, dispatch a prompt to one, wait for it to finish, and collect
its result.

All commands run through `scripts/orchestrate.sh`, against a tmux server on this
machine.

**Name the session in every target.** A pane id (`%3`), a window id (`@5`), a
session id (`$1`), or `session:window` (`myapp:worker-1`) each says which
session it belongs to, so it resolves in any shell. A bare window name
(`worker-3`) needs `$TMUX` set to say which session it means, and an agent's Bash
calls do not reliably carry `$TMUX`. So naming the session is the standing habit,
not a fallback for cross-project sends. With `$TMUX` absent the script refuses a
bare name and names the forms that work; it never claims you are outside tmux.

## Commands

`send`, `send-raw` and `enter` check the target's foreground process before
typing. They refuse with a non-zero exit and name the process when it is neither
a shell nor an agent CLI. Read the pane before deciding how to return it to a
shell or agent.

- `panes [session]`. List every pane in a session: pane id, window, running
  command, pid, title. Its WINDOW column supplies the `<target>` below. A name
  reads any session on the server (`panes myapp`), which is how a
  fleet-level foreman sees another project's board. A wrong name fails loudly,
  the safe failure. Bare `panes` reads your own session and so needs `$TMUX`
  set; without it, name the session. Cross-session `send`/`read` targets carry
  the session prefix: `myapp:worker-1`.
- `send <target> <text...>`. Type text, pause, press Enter, then verify the
  prompt actually submitted (retries Enter once if the pane stayed static).
  Reports `submitted` on success, `WARNING ... UNSUBMITTED` + pane tail on
  failure.

  **Your message crosses two layers before the agent reads it, and each mangles
  a different thing.** The **shell** command-substitutes backticks and `$(...)`,
  so the wrapped word vanishes with only a `command not found` on the way past.
  Name code plainly (*the useActionState state*), and keep `$VAR` out. The
  **composer** treats every newline as its own paste, so a multi-line message
  arrives spliced: numbered points fuse, and fragments of whatever already sat in
  the box splice into yours. So: one line, no backticks, no `$(...)`; use `;` or
  `—` where you wanted a break.

  **One `send` per shell call.** Three chained into a single command hit the
  two-minute tool timeout partway through, and the kill landed mid-sequence: one
  pane held its prompt, one had received nothing, and one held the text pasted
  three times over, unsubmitted. Issue each `send` as its own call and read its
  `submitted` line before sending the next.

  **A long message collapses into placeholders you cannot read back.** Around
  ~2,900 characters, a send arrives as `[Pasted text #N]` chunks. There is no
  way to confirm the text is complete before submitting. Keep the message short
  and put the detail in the ticket, which the worker reads itself. A *new*
  worker never hits this: its task is passed on the launch line as an argument, so
  this governs sends into a pane that is already running.
- `send-raw <target> <text...>`. Type text WITHOUT pressing Enter.
- `enter <target>`. Send a bare Enter.
- `read <target> [lines]`. Print last `[lines]` (default 200) of the pane.
- `capture <target>`. Dump the pane's full scrollback.
- `wait-idle <target> [stable] [poll]`. Block until the pane's output is
  unchanged for `[stable]` seconds (default 3), polling every `[poll]`s.

## Addressing panes: the window name is the address, the `-n` name is the ticket

A window's name is the **address** the manager set: `claude-worker-2`,
`foreman`, `director`. It says which pane this *is*, permanently: `panes` lists
it, `send`/`read` take it as a target, `PREFIX+W` shows it to the human, and it
outlives every round the pane runs. **The address belongs to the manager.**
Name a window once when you create it, and leave every existing name alone
(his ruling, 2026-08-06: agents renaming his windows to ticket handles took his
own labels off his board).

The **ticket handle** travels in the agent's **`-n` name** at launch, and the
pane title renders it. That handle is `billing-v2->28`: thread then arrow then
ticket **number**, fixed at birth on the tracker. So the board reads as two columns:
the window name says *which pane*, the pane title says *what it is building*.
Each string has one job, and only the handle ever changes.

The handle must be right at launch, because nothing corrects it later. A pane
title once read `billing-v2->dark-mode`, a slug instead of `28`, naming a round
that had already merged. The director's report looked like
it named a different pane. Take the handle off the tracker, number never a slug.

Read the names in `panes` before dispatching. Ids say nothing about whose window
a pane belongs to, and a ticket typed into the human's own window looks exactly
like a delivered one.

When a report names a worker, state the pairing once,
`claude-worker-2 (search-api->11)`, so the human can act on either string.
Fall back to the pane id (`%14`) for a window that is unnamed, or that holds
several panes so its name is ambiguous. Addresses and ids both last a
pane's lifetime; numeric indexes (`3.1`) shift as panes close.

## Typical loop

1. `panes` to read the board: addresses and, per pane title, the round each is on.
2. `send claude-worker-2 "<task prompt>"`. Proceed only on `submitted`
   (see caveats).
3. `wait-idle claude-worker-2 4` to let the worker finish.
4. Collect the result: from the transcript for agents (below), or
   `read claude-worker-2 300` for plain CLIs. Act on it, then `send` the
   next instruction.

## When panes hold agents: steer via the pane, read via the transcript

A pane is a viewport, not a log. `read`/`capture` return whatever is painted
on screen: width-wrapped at pane size, mangled by TUI redraws, and holding less
text the smaller the pane or larger the font. Steering through the viewport is
reliable; reading an agent's answer through it is not.

Routes for getting an agent's output, most reliable first:

1. **Headless call.** For request/response, skip the pane entirely:
   `claude -p "question"` or `codex exec "question"` prints the complete
   answer to stdout. If the peer agent exists only to answer questions,
   prefer this over a pane.
2. **Transcript files**, the lossless record of an interactive agent's
   conversation:
   - Claude Code, where your workers are: `~/.claude/projects/<project-slug>/*.jsonl`,
     one folder per worktree, since each worker launches into its own. Newest file is
     the current session; each line is one JSON message (messages, tool calls,
     results).
   - omp: `~/.omp/agent/sessions/<project-slug>/*.jsonl`,
     same one-JSON-object-per-line shape, different keys: a turn is
     `{"type":"message","message":{"role":…,"content":[…]}}`.
   - Codex: `~/.codex/sessions/`.
   Steer with `send`, then read the reply from the transcript, not the pane.
3. **Mailbox files**, long-running peers read and append agreed files
   (e.g. `inbox/<agent>.md`). Durable across restarts and server crashes.
4. **`read`/`capture` the viewport**, supervision only: is the worker stuck,
   sitting on a permission prompt, erroring? Approximate text is fine there.

## Monitoring a working pane

Every pane that is working gets its own background waiter, re-armed the moment it
fires. Waiters die in batches when they deliver, and that is the task queue
emptying, not the work finishing.

**Fire on three conditions together, and say which arm fired**, because *it moved and
went quiet* and *it finished* are different claims:

1. **Grown past its baseline**, and the sharp form of "grown" is
   `git rev-list --count main..HEAD` in the worktree. Zero commits on the branch
   means **nothing was built**: a still, clean worktree at the base commit is
   `NOT-STARTED`, never `READY`. Those are opposite claims and *still + clean*
   is true of both. A worker interrupted before its first edit sits exactly
   like a finished one. A transcript baseline can be faked by any pause; a
   commit count cannot.
2. **Quiet long enough**, and the threshold depends on the tree. A **clean**
   tree earns a 2-minute window. A **dirty** tree gets a much longer one
   (~5 minutes) and fires **once, as a stall**, never on a repeating timer. A
   worker mid browser-verify is legitimately still and legitimately dirty for a
   long time.
3. **No agents in flight.** A quiet transcript and an end-of-turn marker **both
   lie, in opposite directions**: a foreground sub-agent blocks the turn while
   the transcript sits silent, and a background sub-agent ends the turn
   mid-round. Check for agents in flight before believing either, with a
   detector proven as below.

**Prove every detector against a pane you know is idle before you arm it.** The
UI's patterns drift, and a rotted one fails silently, which looks exactly like
*still working*. The footer's agent count is one: finished workers showed
`← 1 agent` on 2026-08-19, and idle ones show `← 3 agents` on 2026-10-12, so a
waiter keyed on it never fired and ran its whole 55-minute timeout blind. A
running turn shows a spinner with an elapsed timer, `✻ Billowing… (27m 42s · …)`.
Build arms on facts the UI cannot rot: the commit count above, `git status
--porcelain` for clean, and a hash of the pane tail compared across two polls
for quiet.

**Gate every text arm on stillness.** A text arm fails the other way, firing on
words that are only passing through. A grep for `went to sleep` fired on a worker
mid-edit, because it was reading a document that quotes the notice; a loose
`Error: ` arm does the same on any pane editing code with that word in it, every
poll. Believe a string only once the tail hash has held still across two polls,
anchor it to the notice's own wording at the start of a line, and fire once per
still streak.

## The pane belongs to the shell

Every launch here puts a **shell** in the pane and sends the agent command into it,
which is what leaves a pane reusable. An agent handed straight to `split-window` or
`new-window` becomes the pane's own process, and with `remain-on-exit off`, the
default, quitting it **destroys the pane**, taking the window when it was the last
one.

```bash
W='claude-worker-6'                                    # the address — named once, at creation
tmux new-window -n "$W" -c /path/to/repo               # a shell, at that address
tmux set-window-option -t "$W" automatic-rename off
```

**Pin the name with that third line.** `automatic-rename` is on by default, so an
unpinned window renames itself to whatever runs: `claude.exe` while the agent
runs, `fish` the moment it quits. The address is gone exactly when an agent
quits, which is when the board matters most.

**The ticket handle goes in the launch's `-n`**, never in the window name. Quote
it there: `>` inside the quotes is literal and safe, unquoted it is a redirect.

### Start the agent inside the workspace it will use

These are the Claude Code launch recipes. For Codex, follow the rulebook's
*Panes and dispatch* exception: launch with `-C <worktree>` in place of
`EnterWorktree`, using the current harness and model routing there.

**A worker's working directory is fixed at birth**, the way a ticket's handle is.
`cd` inside its shell commands moves those commands; it never moves the agent. A
worker launched in the shared checkout therefore stays rooted there for life. Its
status line names the trunk branch, and every relative path it forms resolves
against the trunk.

Carve the workspace out from the pane's own shell, but stay put, at the repo
checkout, to launch:

```bash
H='billing-v2->28'                                     # the ticket handle, from the tracker
send "$W" "git -C /path/to/repo worktree add /path/to/repo/.claude/worktrees/<slug> -b <branch> main"
send "$W" "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false CLAUDE_CODE_DISABLE_WORKFLOWS=1 claude -n '$H' --permission-mode auto 'EnterWorktree /path/to/repo/.claude/worktrees/<slug>, then <task>'"
```

`git -C` keeps `worktree add` running against the repository while the pane sits
wherever it likes, so the prompt that follows describes only the work. The
workspace is already there to receive it, but the pane's shell never `cd`s into
it: launching `cd`'d into the worktree, or from its parent folder, both fail to
bind (a pane experiment measured both, g25 round 2). The worker's own
first act, before any build action, is `EnterWorktree` by that path, named before
the task on every launch line (g25 triage, 2026-10-24,
`overlay/log-ruling/LEDGER.md` §2, shyrosa#45). From inside
`.claude/worktrees/` the call lands with no dialog; anywhere else it prompts
under auto mode, once per entry. Both resume shapes, the fix-round `--resume`
and the reboot-restore `-r`, drop the binding silently, so every resume is
followed by the same re-enter before the next build action.

**`CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false CLAUDE_CODE_DISABLE_WORKFLOWS=1` opens every worker launch line** (the workflows half at his word, g16, 2026-08-21; a director may omit it for an orchestration-shaped ticket)
(the manager's ruling, 2026-08-06). It turns off the composer's ghost
suggestions for that session only, so text in a worker's composer is always
somebody's real typing, while the manager's own windows, and the director's,
keep the feature he likes.

The binding's limits and the worker's duty to aim every write live in the
rulebook's *Panes and dispatch* (g25 triage, 2026-10-24,
`overlay/log-ruling/LEDGER.md` §2). The status line names each pane's real branch.

**Confirm the round started by the artefact, not the spinner.** The worktree is
created a step before the agent, so its absence means the send failed rather than
the agent did. A pane can render a busy spinner for minutes after dying on an
API error, with no worktree behind it. And after dispatching workers in
parallel, **verify their isolation held**: `git worktree list` from the main
checkout, one worktree per ticket. Two workers sharing the trunk HEAD edit the
same files; stop their git and split the work onto per-ticket branches before
anything is committed.

## Recycling a worker pane

A worker recycles between tickets by **quitting and relaunching**. The window
keeps its address, and the next ticket arrives in the new launch's `-n`:

```bash
send "$W" "/exit"                                      # back to the shell
H='search-api->11'                                     # the next ticket's handle
send "$W" "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false CLAUDE_CODE_DISABLE_WORKFLOWS=1 claude -n '$H' --permission-mode auto 'EnterWorktree /path/to/repo/.claude/worktrees/<slug>, then <task>'"
```

The pane title follows the new `-n` on launch, so the board reports the running
round with the window name untouched.

Relaunching is what makes an **edited skill or setting reach the worker**. A
running agent keeps the skills it booted with, and clearing context never re-scans
them. It also leaves the pane at a shell, so `pane_current_command` reads `fish`
and answers *is this pane free* outright, where a cleared agent looks identical to
a busy one. That test is honest only for shell-first panes: a window created with
the agent as its own command reports `fish` even while the agent runs. The launch
form *The pane belongs to the shell* exists to prevent exactly that, caught reporting a working
director as free on 2026-08-06. In doubt, `ps -t` the pane's tty.

Send `/exit`, not a bare `exit`. Both quit immediately, and only the slash form
cannot be read as a prompt.

**Quitting starts the next ticket.** A further round on the ticket just built, a
gate finding or a fix, resumes that agent's prior session instead
(`claude --resume <id> --model <copied> --effort <copied> --permission-mode <copied>`),
which still holds why it built things that way. Copy each value from that session's
launch settings, as `scripts/restore-agents.py` does for reboot restore. A bare
resume can reset effort to the account default. Check the footer after resuming,
then repeat the worktree entry step above before any build action. Quitting
never destroys a session, so the choice is the director's after reading the
report, not the worker's.

The relaunched agent begins a NEW session: the transcript file rotates, so
re-resolve the newest `.jsonl` before reading replies. The old file will never
grow again.

## Relieving an agent in place

Recycling suits an agent holding nothing worth keeping. When its context **is**
the valuable thing, mid-work or a gate finding only it can fix, **relieve** it
instead, inside its own window, so nothing needs renaming or moving:

```bash
tmux split-window -t "$W"                              # a shell beside it, at the repo checkout
H='search-api->11.2'                                   # the ticket handle, indexed for this relief
send <new-pane> "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false CLAUDE_CODE_DISABLE_WORKFLOWS=1 claude -n '$H' --model <copied> --effort <copied> --permission-mode <copied> 'EnterWorktree /path/to/repo/.claude/worktrees/<slug>, then read the handoff at <path> and pick up'"
send %17 "/exit"                                       # quit the spent agent, once the newcomer confirms
tmux kill-pane -t %17                                  # then its pane
```

A relief successor takes the same first act as any dispatched worker: it binds
to its predecessor's worktree by `EnterWorktree` before touching the handoff, so
the binding survives relief the same way it survives a resume.

**The ticket and its address don't change; the handle carries a relief index.**
Relief swaps who is working the ticket, not which ticket it is nor which pane
holds it. The newcomer launches at the same address, in a shell that stays at
the repo checkout, and takes its predecessor's worktree through the entry step
above, since a working directory is fixed at birth.
Its `-n` handle stays the ticket's, with an index appended after a dot
(`search-api->11.2` for the second agent on it); the shape lives in the
glossary's `handle` entry, and the rule that derives the index in
`relieve-and-handoff`. Each `<copied>` is the spent session's own value: model,
effort, and permission mode; the copy rule and its read paths live in
`relieve-and-handoff`.

The survivor expands to fill the window, whose index and name are untouched.
**Split first, kill last.** That order is what lets you verify the newcomer read
the document while the predecessor is still there to fall back on.

**Quit before you kill: killing a pane ends only the view.** The session runs on
without it, and its background jobs, waiters, watchers and standing authority run
on too. On 2026-09-02 a relieved director whose pane was killed ran unseen for
about seven hours, committed to main, and nearly merged beside its successor.
`/exit` ends the session and what it started; if it asks whether to keep
background tasks, end them. Re-arm what the work still needs from the newcomer.

The launch line reaches the pane through a shell, so the **two layers** above
apply to its quoted prompt too.

`relieve-and-handoff` owns when to do this, and how to tell an agent is ready for it.

## Notes & caveats

- **Sent ≠ submitted.** TUI prompt editors buffer a fast keystroke burst like a
  paste and can swallow an immediately-following Enter into it. The prompt
  sits unsent in the input box while the sender believes it was delivered.
  `send` defends against this (pause before Enter, verify the pane reacted,
  one retry), so never report a prompt delivered unless `send` printed
  `submitted`; on WARNING, `read` the pane tail and look before retrying.
- **Idle ≠ done.** A worker blocked on a permission/confirmation prompt is as
  static as a finished one. After `wait-idle`, `read` the tail to distinguish
  finished from waiting-on-approval before concluding.
- **Text on a pane's `❯` line is the human's or a prompt suggestion. Judge it
  with styling in view.** The skill's `read` strips styles, which is why the two
  used to look identical; capture with escapes instead:
  `tmux capture-pane -e -p -t <address> | tail -8`. Composer text wrapped in the
  **dim** code (`ESC[2m … ESC[0m`) is Claude Code's generated suggestion and the
  pane is **free**. `send` normally, and your text replaces the suggestion the
  way the human's own typing would. Text in the **default style** is the
  human's: leave it exactly as it sits and send elsewhere; only when that one
  pane is genuinely the one you need, ask whose text it is. Never submit it and
  never `C-u` it. One ran a round on instructions nobody gave, the other wiped
  his half-typed sentence. Worker panes launched by this skill never show
  suggestions (every launch line opens with the off switch), so any text in a
  worker composer is real.
- **Test a tmux config on an isolated socket, never the live server.**
  `env -u TMUX tmux -L cfgtest -f <conf> new-session -d`, then
  `env -u TMUX tmux -L cfgtest kill-server`. The `env -u TMUX` is mandatory:
  inside a pane, the inherited `$TMUX` silently targets the LIVE server despite
  `-L`. Verify isolation before creating anything. A fresh server starts pane
  ids at `%0`, so higher ids mean you are on the real one. A config test once
  ran `tmux kill-server` bare and destroyed the manager's running fleet
  (2026-07-10); kill only sessions you created, by name.
- **The launch flag and the serving model can come apart, in both directions.**
  One pane launched `--model opus` switched itself to a stronger model a minute
  in; another launched with a model recorded as unavailable came up serving it.
  After any launch that names a model, read which one actually answered: the
  pane's own status line, or the transcript's `model` field. Report that,
  not the flag you passed.
- **A permission classifier can refuse a launch flag.** `--permission-mode
  bypassPermissions` was blocked on a launch line whose identical twin with
  `auto` passed (2026-08-07). Report the refusal and let the manager grant the
  permission. A silently substituted weaker mode is a different session than
  the one that was ordered.
- **Failed ≠ didn't run.** An omp sub-agent returning `failed (exit 1)` with
  `schema_violation` did the work and lost it on the way back: omp discards a
  reply missing any required field of the `outputSchema` its caller attached,
  in `permissive` mode as readily as `strict`. What survives is the error's
  `data` field, cut at 500 characters mid-sentence. Read what is there, then
  re-run that sub-agent for the rest; the cut gives no sign of how much is
  missing. Bit `/code-review`, whose two axes both found real problems and both
  showed as failures.
- `wait-idle` is heuristic (detects "no new output"). For long tool runs raise
  the stable threshold, e.g. `wait-idle 'billing-v2->28' 8`.
- Everything is scoped to the current tmux session by design.

## Setting up worker panes

Workers run **Claude Code**, launched by the line under *Start the agent inside
the workspace it will use*, with `--model` and `--effort` from the rulebook's
ladder. A launch that would open another harness, or a model or provider the
ladder does not name, is a question for the manager before you dispatch (the
rulebook's *Panes and dispatch*). Read the model off each pane's status line
right after launch.

**Three workers build at a time.** Count the panes already working before you
dispatch, and hold at three. Panes beyond those three are **reserve**: kept free for
an emergency, or holding a session you'd rather not clear so you can return to it
later while a review runs in the director. A reserve pane is idle by design, not
spare capacity, so a fourth ready ticket waits for a worker to finish.

Dispatch into these panes as **`/implement`**.

**Confirm the skill landed.** Two signals in the worker's transcript answer two
different questions:

```bash
S=$(ls -t ~/.claude/projects/<worktree-slug>/*.jsonl | head -1)
grep -oE '<command-name>/?[a-z:-]+</command-name>' "$S" | sort -u   # what you dispatched
grep -oE '"skill" *: *"[a-z:-]+"'                  "$S" | sort -u   # what it reached for itself
```

`implement` missing from the first list means the dispatch never landed: quit the
agent and relaunch it with the task. The skills `implement` drives are
model-invoked, so they surface only in the second list, and the review is judged
from there. `tdd` is hedged in `implement` ("where possible, at pre-agreed
seams"), making its absence a call the worker made rather than a fault.

Then from your orchestrator pane, use this skill to coordinate them.
