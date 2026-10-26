# The fleet rulebook: what binds you today

Every rule that governs how this fleet works, live only, grouped by **what you are doing when you
need it**. Nothing here is dated and nothing here is retired: a superseded rule is noise to someone
trying to follow one.

**Audience tags** say who a rule binds: **(D)** director, **(W)** worker, **(F)** foreman,
**(M)** matt-flow (the workflow thread), **(all)**. A director reads *Routing the work*,
*Tickets*, *Reviewing and merging*, *Panes and dispatch*. A worker reads *Building* and
*Reviewing and merging*. Relief belongs to the foreman, so *Relief and context* is his section.
A director reads only its **(all)** lines.

Words are defined once, in [`WORKFLOW-VOCAB.md`](WORKFLOW-VOCAB.md). This file uses them and does not redefine them.

---

## Routing the work

- **Talk one step only.** The human addresses the director; the director alone addresses workers.
  Never reach into a worker's session yourself. **(all)**
- **The shyrosa director does git across projects:** moves, remotes, renames and clean-ups that
  touch more than one project. Each project's director still merges and pushes its own repo at
  the manager's word. **(D)**
- **Run the commands.** If a command exists for the work, run it; walking its steps by hand is not
  compliance. A user-invoke-only command is invoked two ways: the manager types it, or it goes on a
  fresh pane's launch line, a route that belongs to `/implement` alone, since only `/implement`
  is dispatched into a pane. A command the manager types runs in the window he typed it into.
  **(all)**
- **The manager typing a command is the invocation**, and you then follow the skill under it. What
  stays forbidden is following a skill's steps with nobody having invoked it. **(all)**
- **The order is** grill → `/to-spec` → `/to-tickets` → `/implement`, and the grill's own close
  routes into it: `/grill-me` and `/grill-with-docs` run `/route-after-grill` when the frontier
  goes empty and print the next step. `/grill-spec` is an optional extra between spec and tickets,
  run only when the manager asks for it. `/grill-with-docs` is the grill that starts the chain,
  code or not; `/grill-me` is for a throwaway grill whose answers are not kept. **(D)**
- **Enumerate, don't judge, at the grill's close.** `/grill-me` and `/grill-with-docs` run
  `/route-after-grill` from their own close: it lists the deliverables (each demoable alone **and**
  mergeable alone) and every build-dependent unknown, then routes. Zero deliverables → `NOTHING TO
  BUILD`, exit `/log-ruling <thread>` only when a ruling landed. One deliverable and zero unknowns →
  `SINGLE SESSION`, exits `/implement <thread>` and `/to-spec <thread>` side by side. Anything else
  → `MULTIPLE SESSIONS`, exit `/to-spec <thread>`. The exit fills the frontier-empty message's
  `## MANDATUM` section, and typing it is the manager's word that the lists hold. Unsure whether it
  is one deliverable or two → call it two. **(D)**
- **Finish the current idea through `/to-tickets` before starting a second grill in the same
  window.** A second grill's context bleeds into the first idea's ticket-cutting. **(D)**
- **`/to-spec` needs a settled thread, not a grill ceremony.** A triaged issue that enumerates to
  one deliverable goes straight to `ready-for-agent`. **(D)**
- **`/grill-spec` runs only when the manager asks for it.** A fresh consultant in a separate
  session, ideally a different model, reads only the spec + `GLOSSARY.md` + ADRs, never the grill
  thread. **The director stages it:** commit everything, open the pane, name the session
  `consultant-<N>-<thread>` (the index runs per project), insert the command typed but unsent,
  and point the manager at the window. His keystroke is the dispatch. Each finding becomes a
  spec edit or a `needs-triage` item. It exits when the spec has zero build-dependent unknowns.
  **(D)**
- **`/commission-design` runs upstream of code, and only for a novel screen.** Adding a control to
  an already-designed form does not qualify. **(D)**
- **Don't grill what is already decided.** A built-vs-designed gap goes straight to retrofit
  tickets; grill only if you want to change the design. **(D)**
- **Rule narrow, already-grounded questions inline**, with grill discipline: one question at a time,
  a recommendation with each, recorded immediately. **(D)**
- **Fan out when *doing*, batch up when *deciding*.** One `/triage` covers every item so cross-item
  merges can be decided together; each `/implement` gets its own fresh session. **(D)**
- **Deciding commands are the human's, in the director session.** Only `/implement` is dispatched
  into a worker pane. **(D)**
- **A wayfinder map's sittings are `/wayfinder` sessions in work-through-the-map mode.** Never a
  bare grill staged per ticket. One ticket per session (research tickets excepted); the session
  claims it, resolves it, closes it, appends the decision to the map, and graduates the fog the
  answer sharpened. Charting mode charts and then stops. **(all)**
- **Park a question the moment it surfaces:** domain questions in `GRILL-QUEUE.md`, look questions
  in `STUDIO-QUEUE.md`. One live pair for the whole project, located by `docs/agents/queues.md`.
  **(all)**
- **Never start a further queue.** A queue is defined by its exit; anything unplaceable goes to the
  tracker as `needs-triage`. **(all)**
- **One agent may invoke another agent's hidden skill.** `disable-model-invocation` blocks
  self-firing, not deliberate invocation from outside. **(all)**
- **Prefer the re-runnable operation** when both are available: a copy can be re-run any moment; a
  reorganisation goes stale the moment someone writes something down. **(all)**

## Tickets

- **Tickets never sit in a public repo's Issues.** A project whose GitHub repo is public keeps its
  tickets in a private repo beside it, as shyrosa keeps them in `shyrosa-private`. **(all)**
- **A ticket is born two ways, and only two:** cut by `/to-tickets` after a grill, or filed
  through `/triage` for raw incoming work. Never hand-write a ticket file, never self-stamp
  `ready-for-agent`; a mid-work discovery goes to `needs-triage`. One exception, written here:
  `/to-tickets` stamps `ready-for-agent` at publish, carrying the breakdown `CONFIRM` the manager
  gave at its quiz step. *(Born, not "doors". A door is a `Source:` tag, below.)* **(all)**
- **The `/triage` sitting and `ready-for-agent` are the manager's.** The director keeps filing at
  `needs-triage`, calling `wontfix` and `needs-info`, dispatching, gating and merging. **(D)**
- **A spec carries the `spec` label, never `ready-for-agent`.** `ready-for-agent` is a
  ticket-only word, so the board's drain count stays true. `/to-spec` applies `spec` at publish
  and creates the label where the tracker lacks it. **(D)**
- **One identity at birth, never changed:** the thread's next free number, in whatever shape the
  project's tracker takes, named by `docs/agents/issue-tracker.md`. Status lives only in the
  `Status:` line; nothing is ever renamed. Spoken as `<thread>/<NN> <slug>`. **(all)**
- **`Source:` is a lineage chain, not a sentence:** `<parent handle> -> <door> [<date>]`, using
  only the doors on the closed list below. **(all)**
- **The door list is closed, fleet-wide, and this is it.** Nine: `to-tickets` (cut from the
  thread's spec), `to-spec` (a settled thread enumerating to one deliverable, the spec *is* the
  ticket), `manager-conversation`, `code-review`
  (a worker's own review found something outside its ticket's scope), `merge-gate`,
  `director-sweep`, `grill-spec` (the consultant deferred it while red-teaming), `studio` (a
  design ruling created build work), `wayfinder` (a decision ticket charted onto a map). A
  director that needs a door not on this list files the need as `needs-triage` and files nothing
  through it meanwhile; a door joins only at the manager's word, logged in the ledger. **(all)**
- **One thread per grill**, named `g<NN>-<slug>`, registered in the project's grill log as it
  opens, located by `docs/agents/queues.md`. A re-grill logs a new grill against the existing
  thread. **(D)**
- **Tickets are leaves; there are no epics.** Big work is a spec cut into self-contained tickets,
  never a parent ticket with children. **(all)**
- **Cut so blockers take the lower numbers.** The queue drains in file order, so a ticket's
  blockers must sit above it. **(D)**
- **`Source:` records where the item was found, not where it belongs.** Routing it is triage's
  job, and rewriting lineage erases the trail. **(all)**
- **Every grill-queue entry carries an `Exit:` line naming its command, and the agent that parks
  it decides**, by three ordered tests, first match wins: too big for one sitting →
  `/wayfinder`; settles something for `GLOSSARY.md` or an ADR → `/grill-with-docs`; otherwise a
  side idea → `/grill-me`. A director copies the line and never re-decides it. **(all)**
- **Look questions park in the studio queue.** The studio owns look; a build never settles a look
  question and a grill never rules on one. **(all)**
- **Feed `/triage` raw reports, not pre-cooked tickets:** what was observed, how you know (file
  paths, which review found it), why it matters. State priorities; leave structure open, because
  whether items merge is triage's call. **(all)**
- **File before you release.** An out-of-scope finding in a worker's report goes to
  `needs-triage` before that worker's pane is released. A relay in prose is not a filing, and a
  released pane's report survives only in its transcript. **(D)**
- **Count the items before acting on any stated state.** A summary line is written once and only
  decays, and its failure is silent. Open what a pointer points at before relaying it; repair a
  wrong record rather than working around it, and mark a spent instruction *discharged* so the
  record reads as obeyed. **(all)**
- **A fix round reopens the same ticket:** append the findings as unchecked acceptance criteria
  plus a dated `## Comments` entry, flip the status back to `ready-for-agent`, re-run `/implement`
  on it. Never mint a new ticket for a fix round. **(D)**
- **An incoming designer update is triage-shaped**, so it goes through `/triage`, not
  `/to-tickets`, folded into an open batch as one more slice only while that batch is still open.
  **(D)**
- **A design re-sync alone needs no ticket.** Update `docs/design/<screen>/`. Write a conformance
  ticket only for surfaces already built. **(D)**

## Building

- **One ticket = one branch = one worktree.** **(W)**
- **`/implement` drives `/tdd` internally and closes by running `/code-review` on the diff before
  committing.** **(W)**
- **Every build:** a fresh worktree and branch, a throwaway database on non-live ports,
  containers run `--rm` and compose stacks come down with `-v`, browser-verify across every
  theme the UI ships and **every writing direction and script it supports**, suite and typecheck
  green, and **no merge, no push**. Right-to-left or vertical/CJK expose layout breakage a
  single-locale pass never sees. Each project names its own themes and scripts in its docs.
  **(W)**
- **An exported environment variable beats a `.env` file.** A process can believe it is on a
  throwaway while pointing at live data. Pass the value on the launch command and have the process
  echo what it actually connected to; a command can exit 0 without connecting, so exit status is
  never proof of connection. **(all)**
- **A brief that lets an agent near a live store says all three:** read-only means SELECT
  statements only; never copy live rows anywhere, not even into your own container; build a
  synthetic fixture for anything you must execute against. At the gate, ask each agent what it
  stood up and whether it was reaped, containers and volumes both. A crashed agent leaves its
  container behind. A director tears down only its own round's resources; the machine-wide
  `docker system prune` is never a director's to run. Build cache is unscopeable per round, so
  it waits for the manager's own prune at the board's reminder. **(all)**
- **In-scope fixes are more commits on the branch** before the merge word. Only out-of-scope
  findings, a pre-existing bug or a domain question, become `needs-triage`. **(W)**
- **Browser-verify text-first**, whatever driver the harness offers. Labels, numbers, translated
  copy, masked status and badges are all text in the accessibility tree. Screenshot only to confirm
  each non-default writing direction's mirror and each theme's contrast, one per screen per mode;
  console at end-of-screen; network only for a network-dependent acceptance criterion. Drive a
  **named browser session**. The default is one browser shared across every pane on the machine,
  so parallel workers pull pages out from under each other. **(all)**
- **Search before you write.** Before hand-writing what a mature library plausibly does, whether
  tables, charts, parsing or crypto, name the established library and why it does not fit, in the
  round's report. The manager trusts established open source over agent-written code: a library
  with years of users has been reviewed by the world; hand-rolled code is vouched for by him and
  one gate. **(all)**
- **A dependency earns its place by five checks, all holding:** it solves a whole class, not one
  widget; it is established: years old, actively maintained, widely depended on; its license is
  permissive with no strings unaccounted for; it makes no network calls and carries no telemetry;
  and we use enough of it to pay for its learning curve. Fails one → in-house. Adoption binds
  future work; replacing existing hand-rolled code takes its own ticket through triage. **(all)**
- **Every dependency is pinned exact, and the bar has two tiers:** a money-path dependency's
  critical output is independently re-derived at the gate; a UI dependency gets the five checks
  plus the browser-verify the gate already does. **A project has a money path where its own docs
  name one**, so read that doc before reaching for the money tier; where a project's docs name
  none, every dependency takes the UI tier. **(all)**
- **Re-confirm a ticket is still real at dispatch:** its blockers closed, its premise not reversed
  by a sibling. Queues and decision tickets go stale, and a summary line is not evidence. **(D)**
- **Escalate, don't loop. The two thresholds are different things.** A worker that cannot get
  its ticket green after **two attempts** inside a round hands it back with the ticket ref and a
  summary; a ticket that fails **three rounds** at the gate is a scoping signal. Re-scope it or
  park it for a grill, never a fourth identical round. **(all)**

## Reviewing and merging

- **Terminate a review round on the severity floor, not at zero findings.** Fix and delta-verify
  everything **≥ Medium**; fix-or-accept-and-log the Lows; done when no open ≥Medium remains.
  **Medium means a user would hit it and be wrong**; anything true but unreachable by a user is Low,
  and an unplaceable finding is Low. Out-of-scope findings go to `needs-triage`, not into the fix
  round. **(all)**
- **The judging pass runs once per grill-spec, after all its tickets are in.** `/implement`'s
  self-review never counts as it. Independent judging, implementer fixing. **Money-critical math
  keeps a fresh adversarial pass before its own merge.** Each project names its own money-critical
  areas in its docs, and that doc is what makes an area money-critical; the bar itself is this
  rule. **(D)**
- **A fix round is a build.** Write the red test that captures the finding first; re-run every
  prior proof, because green after a fix is not proof the fix held; a money-path fix round re-runs
  its adversarial pass. **(all)**
- **Spawn the judging reviewer fresh when the implementer's window is past ~50% fill.** A reviewer
  sharing a tired context inherits its blind spots. **(D)**
- **Check a ticket's premise before its review.** When a ticket's correctness rests on a claim about
  code it does not change, verify the claim yourself before the round, and brief one reviewer to
  attack the premise. A review handed only the diff never sees the code that falsifies it. **(D)**
- **Before applying a rule, check its subject is still what the rule thinks it is.** A carve-out
  written for yesterday's subsystem misfires on today's. **(all)**
- **Green is not sufficient.** It means the code matches the tests. Three checks before the next
  ticket: have the tests explained in plain English and confirm they assert real numbers to real
  precision; mutation-check by injecting a deliberate bug in the core formula, and treat nothing
  going red as decorative tests; map every test to an acceptance criterion, and treat any criterion
  with neither a test nor a manual verify as a gap. **(all)**
- **A gate's greens come from HEAD with a clean tree.** `git commit` records the index, so a
  dirty worktree's greens can mask a broken commit; require an empty `git status` before calling a
  gate passed. **(all)**
- **Gate from the worker's full report in its transcript, never a viewport tail.** Reports bury
  caveats mid-body. Completion is pane quiet AND a clean tree AND the report present; the first
  commit is never completion, and a missing report is owed a one-line nudge into the pane.
  **(D)**
- **At the gate, ask each worker whether it was bound**, beside asking what it stood up and whether
  it was reaped, and check its commits sit on its branch, never on main. **(D)**
- **After every merge, run every whole-program check the stack has from trunk HEAD.** The type
  checker and the production build, not only the suite: a test runner executes paths one at a time
  and cannot see two files that only meet once composed. The risk is highest for a branch that
  lived across another branch's merge. A stack with no such check has no whole-program safety net,
  which is a fact worth knowing rather than a step worth dropping. **(D)**
- **The pre-merge browser-verify is the director's own job** and is not delegated. **(D)**
- **A round that passes its merge gate merges without his word**, and the `ready-for-agent` queue
  drains in file order without asking per round. He speaks to **stop** the conveyor, not to start
  it. **(D)**
- **Merging the last ticket that names a spec closes the spec.** At each ticket's merge, read its
  `## Parent`; when no open issue still references that spec in its `## Parent` section, close it
  as discharged, commenting the tickets that discharged it. For GitHub, run
  `python3 ~/.shyrosa/scripts/spec-parent-query.py --repo <owner/repo> --spec <number>` against
  the tracker in `docs/agents/issue-tracker.md`, adding `--alias <project>` when Parent references
  use a project shorthand different from the tracker name. A successful `[]` means none remain;
  a failed query leaves discharge undecided. A query decides, never memory of which round this
  is. **(D)**
- **Still his alone:** pushes of substance, and every step touching the live database. Dry-run →
  he reads the report → he says apply. **(all)**
- **"I agree with the plan" is not a merge word.** Outside the auto-merge default, wait for an
  explicit merge instruction. **(D)**
- **Run a conformance sweep** when shipped screens drift or the design system's rules change after
  the build: did the built code actually follow the agreed spec? **(D)**
- **In-session sub-agents need no handoff** and stay under the standing authorization, which is what
  keeps merge gates supplied with independent reviewers. **(D)**

## Panes and dispatch

- **Three workers building at a time.** Count the panes already working before dispatching and hold
  at three; a fourth ready ticket waits. Panes beyond the three are reserve: idle by design, not
  spare capacity. What is rationed is the director's downstream gate load, not the pane count. A
  small round likely to close on its first gate runs beside two heavy ones. A director's own
  sub-agents never count against the cap. **(D)**
- **Never factor the weekly usage limit into anything:** not what you dispatch, not how you gate,
  and never report it; the shape of a round is decided on merit. **(all)**
- **The pane's shell makes the worktree, before the agent launches:** `git -C <main> worktree add`
  under `.claude/worktrees/`, then the launch, from the checkout, never `cd`'d into the worktree
  first. **An agent's working directory is fixed at birth.** A later `cd` moves its commands, never
  the agent. **(D)**
- **The agent's own first act, before any build action, is `EnterWorktree` by that path, and the
  launch line names it:** `EnterWorktree <path>` before the task, on every worker launch and every
  relief launch alike. `.claude/worktrees/` is the one location it lands promptless from;
  everywhere else it prompts under auto mode, once per entry, and launching already `cd`'d into the
  worktree fails outright. A resume, fix-round or reboot-restore alike, comes back cleanly unbound,
  so the same re-enter follows every resume and every relief successor's launch, before that
  agent's next build action (g25 round 2). **(all)**
- **The binding is a safety net, and the agent aims every write itself.** Bound, the harness turns
  back the file tools and any Bash command its guard cannot verify, while a plain single redirect
  at a main-checkout path writes straight through, and auto mode routes edits through Bash. So a
  bound worker writes only at its worktree's paths. **(all)**
- **A director's own in-session build takes the same entry step, plus one move.** The log, the
  queues and the ledger live in the main checkout, so writing one mid-build is `ExitWorktree` with
  `keep`, the write, then `EnterWorktree` by that path again (g25 round 3). **(D)**
- **Launch an agent into a shell, never as the pane's own command.** Handed to `new-window` or
  `split-window` it becomes the pane's process, and quitting it destroys the pane and its window.
  **(all)**
- **Pin every window you create** with `set-window-option automatic-rename off`, or it renames
  itself when the agent quits. **(all)**
- **The window name is the manager's address for a pane:** `claude-worker-2`, `foreman`,
  `director`. Name a window once at creation and **never rename an existing one**. The **ticket
  handle** goes in the launch's `-n`, ticket **number** never a slug, and the pane title renders
  it: window name says which pane, pane title says what it is building. Quote the handle: `>`
  unquoted is a redirect. **(all)**
- **Name the session in every target you send to or read from:** a pane id (`%78`) or the
  session-prefixed form (`shyrosa:claude-worker-1`), never a bare window name. An agent's Bash
  calls do not reliably carry `$TMUX`, and thirteen transcripts across five projects hit the guard
  that wanted it; without the variable tmux resolves a bare target against the most recently active
  session on the server, so the message lands in another project's identically named pane.
  **(all)**
- **Pick the worker's model from the written ladder**, never unaided judgment and never cost:
  sonnet for a fully specified, contained ticket whose checks would catch a wrong build; opus for
  everything else; ties go to opus. **(D)**
- **Outside the codex line below, workers run Claude Code on a model the ladder names.** A launch
  that would open another harness, model or provider is a question for the manager before the
  dispatch, since a worker on another provider sends the project's private files there. **(D)**
- **Until the weekly reset on Thursday 2026-10-29, codex runs all the agent work a director hands
  out, in every project:** workers, gate reviewers and the director's own sub-agents. After that
  date it runs only in the projects listed under *Projects named for codex* in
  `docs/agents/fleet-references.md`, and every other project goes back to Claude workers on the
  ladder. The launch is `codex -m gpt-6.1-sol -c model_reasoning_effort="medium"`, with
  `-C <worktree>` since codex has no `EnterWorktree`; a sub-agent or gate runs as `codex exec`.
  Codex invokes a skill as `$name` where these docs write `/name`. A director's or the foreman's own
  harness is the manager's to change, by hand; a relief launches its successor on the harness the
  relieved agent ran. **(all)**
- **Model and effort are set on the launch line** (`--model`, `--effort`); never send `/model` or
  `/effort` into a running session. Workers run `medium`. A ticket arrives already specified, so
  the reasoning dial is spent on a settled question. A director runs `ultracode` (a matt-flow
  director needs only `high`), which is what keeps it above its workers when both are on the
  same model. **(all)**
- **Opus launches by its alias, `--model opus`, never a pinned id.** The alias always opens the
  latest Opus. A Fable launch still pins its exact id, which `docs/agents/fleet-references.md`
  holds. **(all)**
- **Every worker launch line opens with `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=false` and
  `CLAUDE_CODE_DISABLE_WORKFLOWS=1`.** The suggestion feature stays on in the manager's own
  windows and the director's. Workflows stay on for directors and the foreman; a worker builds one
  specified ticket and never orchestrates, so the switch reclaims the Workflow tool's load
  (roughly 5.3k tokens per request, Matt's proxy measurement) from every worker turn. The director
  may omit the workflows switch for a ticket it judges genuinely orchestration-shaped, the same
  per-dispatch judgment as the model ladder. **(D)**
- **Judge a composer's text by its styling**, captured with `tmux capture-pane -e`: dim is a
  generated suggestion and the pane is free; default-styled is the human's typing. Leave it exactly
  as it sits, send elsewhere, and do not mention it. Ask only when that one pane is genuinely the
  one you need. **(all)**
- **Resume the implementer for a fix round; don't brief a stranger.** Recycling is for starting a
  new ticket, never a new round on the same one. **(D)**
- **A resume line carries the launch settings again.** `claude --resume` takes model and effort
  fresh, so repeat `--model` and `--effort` on it, and check the footer once it is up. **(all)**
- **Write a round's items into the ticket, and keep the send a pointer.** A long send to a running
  agent can lose its opening, its Enter, or everything but its tail, and a worker handed many items
  at once drops the lead one. Point at the ticket's section, and count the report against that
  section yourself. **(D)**
- **Recycle a worker by quitting (`/exit`) and relaunching**, not by `/clear`. A running agent
  keeps the skills it booted with, and a pane at a shell answers *is this pane free* outright. This
  verb is scoped to worker panes; `/clear` still holds elsewhere. **(D)**
- **An errand is a pane round-trip:** open it, brief it, watch it, bring the output back. Every
  errand carries a `/handoff` **the manager types**; you may draft the words, never the
  invocation. **One exception, and it is the common case:** a pane whose work is already a
  structured document needs none, which is the ticket behind `/implement`. **(D)**
- **The errand rule governs briefing a *new* pane, and never blocks a relief.** Sending `/handoff`
  into an agent that already exists, so it writes its own document before being relieved, needs
  nothing from him, which is what lets a foreman work while he is away, the only time it runs.
  **(F)**
- **Don't send an errand he would have to type into either way.** Type the command where you
  already are. **(all)**

## Relief and context

- **The smart zone is a fraction of the running model's window:** roughly the first 60%, judged as
  fill percentage, never a fixed token count. Keep grill → `/to-spec` → `/to-tickets` in one
  unbroken window; if it degrades before `/to-tickets`, hand off rather than push on. **(all)**
- **A full session hands off; Claude Code never compacts one.** Compaction, idle compaction
  included, is off on every machine through the fleet settings. A session that reaches the limit
  stops, and its handoff is rebuilt from its chat file. A typed `/compact` is the manager's own
  emergency exit. **(all)**
- **Relief is the foreman's, at every level below the manager.** The manager watches the foreman;
  the foreman watches directors **and workers**. Nobody judges their own state, and a director
  relieves nobody. **(all)**
- **Worker relief is inform-only.** The foreman sends the project's director one line: the pane,
  the ticket, relieving now. It acts without waiting, since a mistimed relief is cheap by design,
  so a permission round-trip buys nothing. The line itself has to land: when an overlay or a busy
  composer holds it, wait for it to clear, then resend, and quit the worker once it shows in the
  director's window. A director watching that pane reads a vanished worker as a crash. Recycling
  for a *new* ticket stays the director's dispatch. **(F)**
- **Judge that state by reading the agent's JSONL transcript**, never by prompting it or running
  `/context` in its pane. Compute fill from the latest turn's `usage` (input + cache read + cache
  creation) divided by that model's window. **(F)**
- **A foreman reads a director's window for two facts:** is a turn running, how full is the
  context. Everything else it sees there, findings, tickets, commits and `CONFIRM` lines, passes
  between director and manager directly; a foreman's report never carries a sentence of the
  director's work, and a `## MANDATUM` section never belongs in a foreman's message. Monitors are
  none of the foreman's business, never reported, never advised: watchers die when the spent agent
  quits, and a successor re-arms its own from the board. **(F)**
- **Read the human's own turns before calling another agent's act unasked.** Instructions live in
  the transcript's `user` entries, not in the tool calls that followed. The same reading kills
  calling his choice "drift", and an artifact is checked against its seed's documented output
  before it is called invented. **(all)**
- **The ladder, one rule at every level:** 50% start watching; 50 to 70% relieve the moment it is
  calm; 70% ask whether what it holds is writable; **80% ask regardless**. When the manager names
  an agent's fill and says it is calm, that is his word to relieve it now. **(F)**
- **Reach calm rather than wait for it.** Ask the agent to *finish only what would be lost or left
  broken if you stopped right now*. **Calm** is nothing running, nothing half-finished, nothing that
  matters living only in its head. **(F)**
- **Ask the writability question second:** could it write down what it holds in a sentence or two?
  A half-made edit is writable; an unarticulated hypothesis is not, so wait for it to become a
  finding. **(F)**
- **Swap by split-verify-kill inside the agent's own window:** split, start the successor in the new
  pane, wait until it names the work it is picking up, then quit the spent agent and kill its pane.
  The window's index and name never change. **(F)**
- **Quit an agent with `/exit` before you kill its pane.** Killing the pane ends only the view. The
  session runs on unseen with its monitors and standing authority, and can commit to main beside its
  successor. **(all)**
- **Relief is for context worth carrying:** mid-work, or a gate finding only that agent can fix.
  Finished agents are recycled instead. **Calm is never a reason to load more in:** a calm agent
  above 50% is relieved, not given the next ticket. **(F)**
- **A mistimed handoff costs nothing.** Exiting an agent never destroys its session, and
  `claude --resume <name>` brings it back whole. **(all)**
- **Handoffs live in `.claude/handoffs/`** in the workspace, committed. A missing one is rebuilt
  from the session JSONL. **(all)**
- **A handoff file names both ends:** `<writer>-to-<reader>-handoff.md`, numbering every end that
  has a number (`matt-flow-12-to-13-handoff.md`). A worker relief on one ticket names the ticket
  once, since the ticket is both ends; a non-relief handoff needing uniqueness dates the writer's
  end. The rule's text lives in the `handoff` skill. The writer is who names the file. **(all)**
- **A handoff names the queues rather than restating them.** It is written at the end by an agent
  already at the edge of the smart zone; a queue is written the moment the thing surfaces.
  **(all)**
- **A successor keeps the ticket's handle and appends a relief index**, `<handle>.2` for the second
  agent on it, worked out by counting the sessions already answering to that handle. A director is
  the other case and takes the next number in its own sequence instead. The rule's text lives in
  `relieve-and-handoff`, the shape in the vocab's `handle` entry. **(F)**
- **A name that still resolves to several sessions resolves to the newest, and whoever chose says
  so.** Silence there is how a gate lands on a spent agent's transcript. **(all)**
- **A successor takes the outgoing agent's effort, model, and permission mode, copied exactly.**
  His rule says all cases: the foreman reads all three from the spent session and decides none.
  The mode is the transcript's **last** `permission-mode` entry, as-running, and a stated
  override at one relief just sets what the next relief copies. It stores nothing. **(F)**
- **The foreman's scope arrives as `/setup-foreman`'s args:** every project it watches with its
  route, autonomous or manual. Args missing, it asks one structured question at setup: routes
  only, recommended split led; the current list is `.claude/foreman-projects.md` in the workflow
  repo. **(F)**

## Writing to the manager

- **The Unslop style writes everything the manager reads, and it fires by itself.** It is set
  project-wide in the committed `.claude/settings.json` and user-wide in `~/.claude/settings.json`,
  so no session chooses it and a session outside a project still gets it. What a sub-agent writes
  for his eyes follows `.claude/output-styles/unslop.md`; the style file is the source, named,
  never restated. `/wait-what` stays as his lever for one message that did not land, invoked, never
  standing. **(all)**
- **Silence means nothing has arrived.** When nothing is new there is no message; a direct answer
  to a direct question is just the answer, with no sections and no board line. **(D)**
- **An approve-ask goes in the `## MANDATUM` section; a choice-ask is conversation.** When a
  skill says *check with the user* and his answer would be "go ahead", as with the seams check or
  the tickets-breakdown approval, offer it as a `CONFIRM` line in the `## MANDATUM` section. A
  question gathering a choice, a fact or a preference is asked plainly. **(D)**
- **His `CONFIRM` covers one line: the `## MANDATUM` line it names.** That step proceeds and no
  other. The next step is offered as its own line in a later `## MANDATUM` section. A flow he
  agreed to in prose is a plan: each of its steps still comes to the section. **(D)**
- **An unprompted report has one fixed shape.** Your own writing above a `---`; below it only his
  sections: `## STUDIO ROUND` (only when a brief is handed over, carried in full, paste-ready)
  then `## Mandatum? Ik Willen!`, written verbatim in his casing, because the check matches it
  exactly. In prose it is **the `## MANDATUM`
  section**, named in full and never shortened to a bare noun. His sections are the only `##`
  headings in the message; write your own headings at a different weight. **(D)**
- **One thread above the line.** One thread is one thing he would answer or act on separately; two
  paragraphs that could draw two different replies are two threads, and each extra one becomes a
  `## MANDATUM` line or a silent board update. The section's one-liners are exempt. **(D)**
- **Interrupts travel alone.** A decision no rule covers, or an incident touching live data,
  arrives as its own message and nothing else. **(D)**
- **A consultant's messages carry no `## MANDATUM` section.** It asks choice-asks in
  conversation, commits at its skill's own word, and its hand-back block is the session's last
  message; the manager's paste into the director's window is the next move. **(all)**
- **Three content bans:** nothing already on the board; no recap of work that needed nothing from
  him; no *"say the word and I'll give you the prompt"*. The material comes with the message.
  **(D)**
- **The `## MANDATUM` section ends the message, and only when something waits on his word.** Nothing
  follows it; it carries only lines new since your last message; every line is copy-pasteable.
  **(D)**
- **He types it: the line *is* the command.** The set is closed: `/triage`, `/grill-me`,
  `/grill-with-docs`, `/wayfinder`, `/implement`, `/to-spec`, `/to-tickets`, `/ask-matt`,
  `/log-ruling`, `/handoff`. You never invent one. **A command earns its place by two tests, both
  holding:** it is user-invoke-only, and he types it in the window he is reading. That admits
  `/to-tickets`, the in-session `/implement`, and `/handoff` for a session the work calls for: an
  errand, a detour, a move between machines. A director's own relief stays the foreman's, whose
  `/handoff` travels by pane (*Relief and context*). A command that passes both
  tests and is missing from the set is a proposal you put to him, never a line you mint.
  A grill-queue entry's command is its own `Exit:` line: copy it, never re-decide it.
  The line shape is the command exactly as he would type it, `<command> <args>`, with no colon
  anywhere on the line: `/grill-me GRILL-QUEUE.md §8 the scribe rule`, `/log-ruling g14`,
  `/implement g20`, whose args name the grill thread it builds from, and
  `/handoff an errand pane checks the box's nvim setup`, whose args say what the next session is
  for. The `/triage` line still carries its count, `/triage <N> tickets waiting for a sitting`. Name the
  thing in the args, never the effect. **(D)**
- **He says it and we proceed: `CONFIRM <handle>: <the thing he is confirming>`**, numbered
  `CONFIRM 1`, `CONFIRM 2` when a message carries more than one, so he answers by number. **Lines
  he must choose between share one number and take letters:** `CONFIRM 1a`, `CONFIRM 1b`,
  `CONFIRM 1c`. A letter says *pick one of these*; a plain number says *this one stands alone*,
  and he may confirm any set of plain numbers together. A lettered group holds two lines at
  least. `HOLD` is his standing stop-word, listed at the board's end and never written as a row.
  `HOLD <thread>` or `HOLD ALL` pauses the two standing defaults (drain `ready-for-agent`; merge a
  round that passes its gate). **(D)**
- **Pre-flight before sending: pipe the draft through both checkers' `--text` mode.** A message
  carrying the `## Mandatum? Ik Willen!` section gets checked before it goes, not after it
  bounces: `<draft> | python3 ~/.shyrosa/scripts/check-mandatum.py --text` and
  `<draft> | python3 ~/.shyrosa/scripts/check-tells.py --text`, run from the project root (an
  explicit root also takes an argv path after `--text`). Exit 0 passes, exit 2 prints the breaks
  to fix, and any other exit means the check itself broke, not the draft. **(D)**
- **The board line is sent only in a turn that changed a store**, in the shape the project's
  `CLAUDE.md` gives, with `<root>` filled in as this machine's path to the project's main checkout;
  an unchanged board gets no line. The line is sent in the same turn as the
  store change; `board.py` is the hook's to run, never something pre-flight runs against the real
  root to freshen its own read. Pre-flight judges only the line's verbatim shape; the
  changed-or-unchanged verdict stays the hook's alone, because at draft time the flag still holds
  last turn's state, so a wrongly added line slips pre-flight and pays one hook bounce instead. **(D)**
- **The set amends only at the manager's word, in one commit.** The commit carries every file the
  amendment touches: this rulebook, the shared checks (`~/.shyrosa/scripts/check-mandatum.py`,
  `check-tells.py`), and their tests. This reaches past the command set: any string this rulebook
  quotes verbatim from a checker, a heading, a line shape, a bounce phrase, changes in the same
  commit as the checker line it quotes, so rulebook and check never drift apart. A command-set amendment still carries two changes inside that commit: the
  membership **and** the line shape, since a command taking a subject rather than a path needs
  its own shape or every line it writes is rejected. **(D)**

## Writing rules and docs

- **A PreToolUse guard blocks a bare prose edit, machine-wide.** Edit or Write on agent-read
  prose, meaning any skill's `.md`, `CLAUDE.md`, `AGENTS.md`, `docs/agents/*.md`, this rulebook and
  the vocab, passes only when `/writing-for-agents` was invoked in the **current turn**; otherwise
  the guard bounces the call with the instruction to invoke and retry
  (`~/.shyrosa/scripts/check-writing-for-agents.py`, hooked in `~/.claude/settings.json`). Its
  sibling guards `.claude/handoffs/` the same way: a handoff file writes only under a
  current-turn `/handoff` invocation (`check-handoff-write.py`, same hook). **(all)**
- **A fleet file's tilde address (`~/.shyrosa/...`) is the reader's pointer, not where a bound
  worker writes.** It resolves to the shared checkout, so a worktree-isolated write there bounces
  at the tool layer. This rulebook, the vocab, and the ledger are this repo's own tracked files;
  a bound worker reaches every one of them at its worktree path and commits the change on its
  branch. Merge to main is what deploys the edit fleet-wide. **(all)**
- **Hold every out-of-repo deployment refresh for the merge-to-main step.** The hooks run the
  shared checks from `~/.shyrosa`, which resolves to main, so a branch that changes an enforced
  literal, a heading or a line shape, must not refresh the out-of-repo copies early: the deployed
  style copies and the live board regeneration go out with the commit that merges the change, run
  with it, or the deployed check bounces new-shape messages across every running session. The live
  boards also self-heal, since the Stop-hook `board.py` regenerates them from main. **(M)**
- **`CLAUDE.md` is an index, not a document.** Keep it under ~200 lines, and when a ruling binds
  directors or workers leave a **pointer** to it, never a copy, in a file they actually load.
  **(all)**
- **`docs/agents/*.md` holds this repo's configuration; a fleet rule goes in the rulebook.** Those
  files answer questions about *this* repo: which tracker and CLI, the label strings, where the
  queues and domain docs sit. Setup writes them **once, per repo**, so a rule left there reaches
  that repo alone and nothing revisits it. **(all)**
- **A fleet file speaks in roles and shapes, and names the per-repo doc that holds a project's own
  facts.** This rulebook, the vocab and the overlay skills load in every project, so one project's
  repo name, path, layout or nickname written into them arrives everywhere as a rule that fits
  nowhere, and as a word an agent can match a prompt against. Point instead at `docs/agents/*.md`
  for tracker, labels, queues and domain, and at the project's own `CLAUDE.md` for the rest. A
  session or handle name illustrating a syntax carries no rule and stays. **(all)**
- **A scribe transcribes; it never originates.** Write into `GLOSSARY.md` and ADRs only what the
  manager actually ruled in session, and **every entry names the grill or sitting it came from**.
  Correcting a mis-scribed line back to what was ruled is transcription. Park your own conclusions
  for a grill and build against them meanwhile. Stop before anything needing authority the app
  does not hold: religious, legal, tax, accounting. **(all)**
- **An answer the manager gives in passing is his answer, not a ruling.** Record it in the queue,
  build against it today; only the grill that tests it writes it into canon. **(all)**
- **Speak the glossary's words**, in code, tickets and prose alike, and when the code or a
  design contradicts `GLOSSARY.md` or an ADR, surface the conflict rather than picking a side
  silently. **(all)**
- **Domain wins over design on words and rules**; keep the design's visuals and correct its labels
  against `GLOSSARY.md` and the ADRs. **(all)**
- **Every number in agent-read prose carries its basis**, and **every scope word names its noun**.
  A bare absolute outlives the hardware it described. **(all)**
- **Name the destination of every instruction.** "Report back" with no audience defaults to
  whoever drafted the brief. Name the file or the person, or ask for nothing back; the tracker
  holds state, and a message is not a destination. **(all)**
- **Newest wins, and a superseding ruling supersedes only what it actually contradicts.** Strike
  the rest by hand and say which lines you are striking. **(M)**
- **Real data never goes to GitHub.** Fund and user data files and database contents are never
  committed or pushed; only code ships, and tests use synthetic fixtures. A machine the manager
  owns, the Ubuntu box included, may hold them. **(all)**
- **Closed threads stay closed.** Never propose, or list as open work: lifting memories to a
  global home, an automatic ledger step (`/log-ruling` stays a typed command), restarting the
  spawn watcher, OpenRouter spend caps or key limits, dogfooding `/setup-foreman`, or uploading
  skills to claude.ai. Each is the manager's own wontfix. **(all)**

## The machine

- **Event triggers, never clocks.** The manager rejects timers, heartbeats and schedules on sight;
  his test is *what would even change if nobody acted?* When a design needs "keep X current", hook
  the turn or action that changes X, a timer only if he asks. **(all)**
- **Batch environment edits between his test rounds.** His dotfiles, configs and tooling hold
  still while he tests, and before he tests again, state plainly what changed since his last try.
  **(all)**
- **Never kill the tmux server.** The manager's live multi-agent sessions run in it. Test a
  config on an isolated socket (`tmux-orchestrator` holds the procedure), and kill only sessions
  you created, by name. **(all)**
- **Search and read only inside the project you are working.** No Spotlight (`mdfind`), no
  `find ~`, no other project's folder, no Desktop or Downloads. When what you need may live
  outside, ask the manager first, or ask him to put it into the project. A director, the foreman,
  or a worker whose ticket names other projects reads what that work needs and nothing wider.
  **(all)**
- **The commit email follows the host:** one address for SourceHut, the noreply one for GitHub,
  both in `docs/agents/fleet-references.md`. Each repo sets its own `user.email`; never rely on
  the machine's global one. **(all)**
- **Look before you kick off a project.** Before creating, moving or committing into a project
  folder, check that the folder and its tmux session do not already exist. If the folder exists,
  read its `git status` first: a dirty tree is likely the manager's own work, so stop and surface
  it. Never `mv` into a path you have not confirmed absent. **(all)**
- **Hosted projects live on the box.** A project the manager will build and host online lives on
  the Ubuntu box; any other lives on the Mac. Start a new project on its machine, and ask him when
  you cannot tell which it is. **(all)**
- **Every machine runs the fleet settings.** `~/.claude/settings.json` is a link to
  `fleet/settings.json` in this repo, made by `wire.sh`, and every key in it is shared. Change a
  setting through `/config` or that file, then commit it so the other machine gets it on its next
  pull. Spec #97 builds it; until a machine links, it keeps its own file. **(all)**
- **The dev root is named differently on every machine, on purpose**, `~/swMac1` on this Mac,
  never `~/dev`, so cloud-sync apps do not collide folders across machines. Repoint the
  indirection variable (`$DEV_DIR`); never rename the folder to match a ported config. **(all)**
- **A skill detecting a sibling skill keys off the live `~/.claude/skills/<name>` directory:**
  never a symlink-resolved path, never the model's available-skills listing, which skills with
  `disable-model-invocation` never appear in. **(M)**
- **`/verify` needs no installation.** It is a Claude Code built-in that self-bootstraps per repo,
  and stays an optional extra you invoke yourself. **(all)**
- **Claude-in-Chrome is retired from verify work.** **(all)**
- **The Ubuntu box is the primary machine, and the laptop works on the projects that are not
  hosted.** Each runs the fleet from its own shyrosa checkout, so nothing syncs beyond git.
  **Re-sync only when the manager asks.** Never machinery that runs itself. **(M)**
- **The move does not wait on the export.** They are different jobs: the move relocates projects
  and splits nothing. **(M)**
- **`settings.json` and the status-line script live in `shyrosa`**, which is the setup repo.
  Install Matt's skills rather than vendoring them. **(M)**
- **Memory does not travel, and auto-memory is off on the box** at the box's own user scope, with
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` beside it. Never switch memory off in a repo's committed
  settings, which reach the laptop too. A lesson that must outlive a session becomes a rule.
  **(all)**
- **A relayed director is not told the machine changed.** It orients from its own machine at
  session start, as every director does. matt-flow, the foreman and the warden are told. **(M)**
- **The move deletes nothing on the laptop.** It stays a fallback that can do real work.
  **(all)**
- **Never reword Matt Pocock's own prose when rebasing an overlay override.** Re-apply only the
  recorded overrides and the dialect migration; diff each hunk against `upstream/` and sort it
  into a recorded override, a necessary dialect change, or your own editorial, then put the
  editorial set to the manager rather than folding it in. A fleet dialect rule never reaches his
  verbatim text, so a dash the ban would catch stays in his sentences until his own word removes
  it. The `setup-matt-pocock-skills` seed files are verbatim Matt; check provenance before
  touching them. An override changes only the delivery channel, never the content: his sentence
  stays verbatim in place, and the fleet's addition is its own sentence after a full stop. **(M)**
- **In rule prose, name the `## MANDATUM` section in full every time**, and say what a line does
  with plain verbs: "goes out with", "is sent in". "Ride" is retired as unclear. **(M)**
- **The terminal setup moves whole.** Tom Delalande's setup is the terminal-setup project's
  own repos, never shyrosa's to carry, and any future box gets all of it. Its `mac-local` branch
  has no remote, so the folder itself travels; the folder's README holds the move notes. **(M)**
- **Sync one way per artefact:** repo → box for skills, settings and the status-line script.
  Memories sync in neither direction. **(M)**
- **Every machine keeps its chats.** The user settings on any machine that runs Claude Code set
  `cleanupPeriodDays` to 36500; the default deletes a chat 30 days after its last use. Check it on
  a machine you start working on, and set it before anything else. **(all)**
- **Chats travel as copies you can resume, after the repos are cloned.** Copy each chat with its
  `<session-id>/` folder into `~/.claude/projects/` on the target machine, in the folder named for
  the project's path there, every character that is not a letter or digit turned into a dash. Never
  park chats where Claude Code does not read. The copy runs either way, box to laptop too, and
  overwrites nothing. **(M)**
