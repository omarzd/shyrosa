# The fleet's words

What the fleet's own words mean. `GLOSSARY.md` is the business domain and holds none of these. It
never says *director*, *pane*, *worktree* or `Status:`, so this file is where a fleet word is
defined, and it is the only place any of them is defined.

**Two kinds of entry.** A word that names a **thing** carries its whole meaning here, because the
thing does not change. A word that names a **procedure** carries its meaning here and then names
the file that holds the procedure. The steps are never copied, because a copy drifts and an agent
following a stale copy acts wrong.

**Two ways in.** Met a word you do not know? Look it up. Need a word for something? **Search this
file first, and where a concept here is close, that is the word.** Naming is a lookup, and this
page is where the answer already sits.

**Nothing fits?** Say the thing in plain words and park the gap. A word joins this list by the
manager's decision, because he is the reader every one of them has to work for.

**Rules are not here.** What binds you is [`WORKFLOW-RULEBOOK.md`](WORKFLOW-RULEBOOK.md).

## Who

- **manager**: the human this fleet serves. He rules; agents recommend. Also called *the human* in
  the older entries; one person, two words.
- **director**: the planning session that owns the backlog: it grills, cuts tickets, dispatches
  workers, runs gates, and merges. One at a time, numbered in sequence (`director-22`), and its
  number never changes for its whole life however often it is resumed.
- **worker**: an agent in its own pane building exactly one ticket, in its own worktree, on its own
  branch.
- **foreman**: a fourth role that owns exactly one thing, handing one director off to the next
  while the manager is away.
- **matt-flow**: the thread that improves the workflow itself rather than the product. Numbered
  like directors (`matt-flow-9`).
- **consultant**: a fresh session that red-teams a spec: it reads the spec, `GLOSSARY.md` and the
  ADRs, never the grill thread that produced them.
- **sub-agent**: a helper an agent spawns inside its own session. It has no pane and no session of
  its own, which is why nothing is ever handed off to it.
- **studio**: the persistent claude.ai/design project that owns *look*. It grills on look and
  returns a design; the domain still owns the words.

## The board

- **pane**: one tmux slot holding one agent.
- **window**: the tmux container a pane sits in. Its **name** is the manager's **address** for that
  pane. That name, `claude-worker-2`, `foreman`, `director`, is what `panes`, `send` and `read` aim
  at.
- **pane title**: what the agent's `-n` name renders as. So the board reads in two columns: the
  window name says *which pane*, the pane title says *what it is building*.
- **speaking of a session**: the agent's own name wherever one exists (`director-28`,
  `foreman-4`), since numbered names self-locate; the window name for anything unnumbered
  (`temp-ask-docker`); the project as a plain spoken suffix only when crossing projects,
  "temp-ask-docker, in my-project". tmux's `session:window` stays command syntax, never
  speech.
- **handle**: a ticket's one spoken name, `<thread>/<NN> <slug>`, fixed at birth on the tracker. In
  a pane's `-n` it appears as `<thread>-><NN>`, the ticket **number**, never a slug. Across a relief
  the handle stays fixed and the successor's pane appends an index after a dot, `<thread>-><NN>.2`
  for the second agent on it, `.3` for the third. The rule that derives the index lives in
  `relieve-and-handoff`.
- **free pane**: one at a shell rather than running an agent, which is what `fish` versus
  `claude.exe` answers.
- **reserve pane**: a pane beyond the three that build: idle by design, kept for an emergency or
  holding a session worth returning to. Not spare capacity.
- **board**: the manager's windows as he reads them. Also the generated view over the tracker's
  stores, which is the thing being built by the readability map.
- **`## MANDATUM`**: the section that ends a message to the manager and holds only what waits on
  his word: commands he types, and `CONFIRM` lines he approves. Its heading is written verbatim,
  `## Mandatum? Ik Willen!`, because the check matches it exactly.
  *Mandatum* is Latin for a command handed down, and it is what a Briton says when you select it in
  Age of Empires II. Its rules live in [`WORKFLOW-RULEBOOK.md`](WORKFLOW-RULEBOOK.md) under
  *Writing to the manager*.
- **approve-ask**: a question whose answer would be *go ahead*. It reaches him as a `CONFIRM`
  line in the `## MANDATUM` section, never as prose.
- **choice-ask**: a question gathering a choice, a fact or a preference. It is asked plainly in
  conversation and never becomes a line.
- **errand**: the whole round trip of sending a pane work and getting its output back.
  Procedure: `docs/agents/fan-out.md`.
- **dispatch**: putting a ticket into a pane so a build starts. Procedure:
  [`WORKFLOW-RULEBOOK.md`](WORKFLOW-RULEBOOK.md) → *Panes and dispatch*, with each repo's own
  facts in its `docs/agents/fan-out.md`.
- **recycle**: ending an agent and starting a fresh one in the same pane, for a *new* ticket.
  Procedure: `tmux-orchestrator` → *Recycling a worker pane*.
- **relieve**: replacing a filling agent with a fresh one that carries its work forward, for the
  *same* work. Procedure: `relieve-and-handoff`.

## Tickets

- **ticket**: one unit of build work, one file, one branch, one worktree.
- **pre-flight**: piping a draft message through the checkers' `--text` mode before sending, so a
  shape break costs one small check instead of a full rewrite; the rule lives in
  [`WORKFLOW-RULEBOOK.md`](WORKFLOW-RULEBOOK.md) under *Writing to the manager*.
- **entry step**: the launch move that binds an agent to its worktree, `EnterWorktree` by path,
  repeated after every resume; the rule and its whys live in [`WORKFLOW-RULEBOOK.md`](WORKFLOW-RULEBOOK.md)
  under *Panes and dispatch*.
- **thread**: the container a grill and its tickets live in, named `g<NN>-<slug>` and registered in
  `GRILL-LOG.md`.
- **`Status:`**: a ticket's only mutable state, and the only place its state is written.
- **needs-triage**: an agent found this mid-work and it awaits the manager's judgment.
- **needs-info**: it cannot proceed until a question is answered.
- **ready-for-agent**: cleared for a worker to build. The manager alone puts a ticket here.
- **wontfix**: closed without building. Reversible, so a director may call it.
- **door**: the named route a ticket arrived by, recorded in `Source:`. The closed list lives in
  [`WORKFLOW-RULEBOOK.md`](WORKFLOW-RULEBOOK.md) under *Tickets*. A door is not how a ticket is
  *born*. Birth is `/to-tickets` or `/triage`, and that rule is the rulebook's too.
- **deliverable**: a unit that is demoable alone **and** mergeable alone. Counting these is what
  decides whether work is one session or many.
- **build-dependent unknown**: a question that can only be answered by building. One of these
  forces the spec path.
- **fix round**: another pass over a ticket that has already been built, driven by findings. It
  reopens the same ticket and never mints a new one.
- **round**: one worker's pass at a ticket, from dispatch to gate.
- **triage**: the sitting that moves raw incoming work out of `needs-triage`. The manager's.
  Procedure: the `/triage` skill and `docs/agents/triage-labels.md`.

## Deciding and building

- **grill**: a relentless one-question-at-a-time interview that settles what is undecided. Facts
  are the agent's job; decisions are the manager's. Procedure: the `/grilling` skill.
- **sitting**: one bounded session that settles something with the manager.
- **AR**, *as recommended*: the manager taking the option an agent recommended, in two letters
  instead of a sentence. He also asks it, *"is that AR?"*, to check whether the answer he just
  gave is the one that was recommended. An agent answers that question straight, including when the
  honest answer is no.
- **spec**: what a grill becomes, written in the same window that grilled it. On the tracker it
  carries the `spec` label, never `ready-for-agent`; `/to-spec` creates the label where missing.
- **map**: a wayfinder's chart of decision tickets for work too foggy to plan in one session.
- **fog**: what the map can see is coming but cannot yet state sharply. Resolving a ticket
  **graduates** whatever the answer sharpened into a real ticket.
- **frontier**: the tickets open right now with nothing blocking them, the edge of what can be
  worked.
- **worktree**: the separate checkout a worker builds in, on its own branch, so no two workers
  touch the same files.
- **browser-verify**: driving the running app to check a ticket, text-first, before it can merge.
  Procedure: `ui-work-browser-verified-before-merge`.
- **gate**: the check a finished round must pass before it merges.
- **merge word**: the manager's explicit instruction to merge. Still required for anything the
  standing auto-merge default does not cover.
- **severity floor**: where a review round stops, no open finding at Medium or above. Not zero
  findings.
- **Medium**: a user would hit it and be wrong. **Low**: true, but no user can reach it, or it
  cannot be placed.
- **judging pass**: the independent review that decides which findings count. Once per grill-spec,
  never the builder's own.
- **self-review**: the `/code-review` that `/implement` runs on its own diff before committing.
  Catches slop; never counts as judging.
- **adversarial pass**: a fresh hostile review, kept for money-critical math.
- **conformance sweep**: the reverse check, did the built code actually follow the agreed spec?

- **ultracode**: the director's effort setting, the `xhigh` reasoning level plus dynamic
  workflow orchestration. The status line reads `ultracode` only when the launch line set it
  (`--effort ultracode`); a session that got it any other way reads plain `xhigh`, and `xhigh`
  with workflows on **is** ultracode. A label gap, not a missing setting.

## Context

- **smart zone**: the stretch of a session where the model still reasons sharply, roughly the first
  60% of the running model's window, judged as fill percentage, never a token count.
- **fill**: how much of the window is consumed, as a percentage. Read from the agent's transcript,
  never by asking it.
- **calm**: nothing running, nothing half-finished, nothing that matters living only in the agent's
  head. The state an agent must reach before it is relieved.
- **the ladder**: the four thresholds that govern relief. 50% watch, 50 to 70% relieve when calm,
  70% ask if writable, 80% ask regardless. Procedure: `relieve-and-handoff`.
- **handoff**: the document that carries one agent's work across a session boundary, written where
  the work currently lives. Procedure: the `/handoff` skill. *(A design handoff is a different
  thing: what the studio returns after a design round.)*
- **transcript**: the durable per-session `.jsonl` record. The lossless way to read what an agent
  did; a pane's viewport is not. The manager calls it a **chat**. Durable only where the machine's
  retention is set, see the rulebook's *The machine*.
- **queue**: a parking place for a question that outlives the session. It is defined by its exit,
  which is why there are only two: the grill queue and the studio queue.
- **park**: write a question into a queue instead of answering it.

## Canon

- **rule-text bug**: a defect in agent-read prose that makes a correct agent behave wrong. Fixed at
  its source, never worked around.
- **bounce**: a hook's loud rejection of a message or tool call, landing in the writer's own pane
  with the repair named; the writer fixes and resends. A bounce that names only the crime teaches
  the wrong lesson, g03's finding.
- **reach**: whether a rule lands in a file the agents it binds actually load. A rule with no reach
  is not a rule.
- **override**: this project's own version of one of Matt's skills, recorded as a diff against the
  pristine copy.
- **scribe**: whoever holds the pen on `GLOSSARY.md` or an ADR. A scribe transcribes what a grill
  settled; it never originates.
- **supersede**: a later ruling replacing an earlier one. It replaces only what it actually
  contradicts.
- **fleet settings**: the one Claude Code user settings file, `fleet/settings.json` in this repo,
  that every machine's `~/.claude/settings.json` links to. A `/config` change on any machine edits
  it, so the machines cannot drift apart. Every key in it is shared.
