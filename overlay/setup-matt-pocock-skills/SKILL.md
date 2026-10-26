---
name: setup-matt-pocock-skills
description: "Configure this repo for the engineering skills: set up its issue tracker, triage label vocabulary, and domain doc layout. Run once before first use of the other engineering skills."
disable-model-invocation: true
hide: true
---

# Setup Matt Pocock's Skills

Scaffold the per-repo configuration that the engineering skills assume:

- **Issue tracker**: where issues live (GitHub by default; local markdown is also supported out of the box)
- **Triage labels**: the strings used for the five canonical triage roles
- **Domain docs**: where `GLOSSARY.md` and ADRs live, and the consumer rules for reading them

This is a prompt-driven skill, not a deterministic script. Explore, present what you found, confirm with the user, then write.

## Process

### 1. Explore

Look at the current repo to understand its starting state. Read whatever exists; don't assume:

- `git remote -v` and `.git/config`: is this a GitHub repo? Which one?
- `AGENTS.md` and `CLAUDE.md` at the repo root: does either exist? Is there already an `## Agent skills` section in either?
- `GLOSSARY.md` and `GLOSSARY-MAP.md` at the repo root
- `docs/adr/` and any `src/*/docs/adr/` directories
- `docs/agents/`: does this skill's prior output already exist?
- `.scratch/`: a sign that a local-markdown issue tracker convention is already in use
- Is the `triage` skill installed? (a `triage` folder in `~/.claude/skills/`.) This decides whether Section B runs at all.
- Monorepo signals: a `pnpm-workspace.yaml`, a `workspaces` field in `package.json`, or a populated `packages/*` with its own `src/`. These are present only in a genuinely large multi-package repo; their absence means single-context, which is almost every repo.

### 2. Present findings and ask

Summarise what's present and what's missing. Then take the sections in order. One section, one answer, then the next.

Lead each section with the recommended answer so the user can accept it in a word. Give a one-line explainer only when the choice genuinely branches; skip the section entirely when exploration already settled it (Section B when `triage` isn't installed, Section C when there's no monorepo).

**Section A: Issue tracker.**

> Explainer: The "issue tracker" is where issues live for this repo. Skills like `to-tickets`, `triage`, and `to-spec` read from and write to it. They need to know whether to call `gh issue create`, write a markdown file under `.scratch/`, or follow some other workflow you describe. Pick the place you actually track work for this repo.

Default posture: these skills were designed for GitHub. If a `git remote` points at GitHub, propose that. If a `git remote` points at GitLab (`gitlab.com` or a self-hosted host), propose GitLab. Otherwise (or if the user prefers), offer:

- **GitHub**: issues live in the repo's GitHub Issues (uses the `gh` CLI)
- **GitLab**: issues live in the repo's GitLab Issues (uses the [`glab`](https://gitlab.com/gitlab-org/cli) CLI)
- **Local markdown**: issues live as files under `.scratch/<feature>/` in this repo (good for solo projects or repos without a remote)
- **Other** (Jira, Linear, etc.): ask the user to describe the workflow in one paragraph; the skill will record it as freeform prose

Record the choice in `docs/agents/issue-tracker.md`. The GitHub and GitLab templates carry a "PRs as a request surface" flag, defaulted **off**. Leave it off and don't raise it: a user who wants external PRs in the triage queue can flip the flag in the file later.

**Section B: Triage label vocabulary.** Skip this section entirely if the `triage` skill isn't installed (exploration told you), since an uninstalled skill needs no labels.

If it is installed, ask exactly one question:

> Do you want to keep the default triage labels? (recommended: **yes**)

The defaults are the five canonical roles, each label string equal to its name: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. On **yes**, write them as-is. Only if the user says no, usually because their tracker already uses other names (e.g. `bug:triage` for `needs-triage`), collect the overrides so `triage` applies existing labels instead of creating duplicates.

**Section C: Domain docs.** Default to **single-context** (one `GLOSSARY.md` + `docs/adr/` at the repo root). This fits almost every repo; write it without asking.

Offer **multi-context** (a root `GLOSSARY-MAP.md` pointing to per-context `GLOSSARY.md` files) only when exploration found monorepo signals. Then confirm which layout they want.

### 3. Confirm and edit

Show the user a draft of:

- The `## Agent skills` block to add to whichever of `CLAUDE.md` / `AGENTS.md` is being edited (see step 4 for selection rules)
- The contents of `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, `docs/agents/triage-labels.md` (that last one only when `triage` is installed), and `docs/agents/fan-out.md`

Let them edit before writing.

### 4. Write

**Fleet wiring comes first, and it is not optional.** Every project set up by this skill joins the
fleet whole, the manager's ruling of 2026-08-13. Write these before the block below, and in
**repair mode** when any already exists: add what is missing, never overwrite what is there, and
report exactly what you added. One exception: a machine path (`/Users/...`, `/home/...`) in
existing wiring is a break, because the same files run on the Mac and on the box. Replace it with
the forms below and report each replacement.

1. **The fleet section in `CLAUDE.md`** (or `AGENTS.md`, per the selection rules below), above the
   `## Agent skills` block:

   ```markdown
   ## The fleet rulebook

   `~/.shyrosa/WORKFLOW-RULEBOOK.md` binds every agent here, including how you write to the
   manager and the `## MANDATUM` section, under *Writing to the manager* there.
   `WORKFLOW-VOCAB.md` beside it defines the fleet's words. Each rule cites its ledger section,
   so the reasoning is one hop away.

   This project's board line is `Board updated: file://<root>/<project>-board.html`, where `<root>`
   is the absolute path of this project's main checkout on the machine you are on. The board check
   builds the same line, so it differs between the Mac and the box.
   ```

   Keep `<root>` as the literal placeholder, so the one line holds on both machines.

   **The board filename is `<project>-board.html`**, the project's folder name, lowercase
   kebab-case (ShyRosa → `shyrosa-board.html`). The `.md` twin shares the stem. The filename
   is what a tab or a file list shows, so it must name the project itself.

2. **The output style**: copy `~/.shyrosa/fleet/unslop.md` to
   `.claude/output-styles/unslop.md`, byte-identical. Never compose it.
3. **The project config** is `.claude/fleet.json`: `tracker` (`"local-scratch"` or
   `"github-issues"`, from Section A's answer) and `board_html` (the board's filename,
   `<project>-board.html`, relative to the project root), `worktree_mark` (`<project>-wt`, the
   folder the project's worktrees sit in, which the board lists as building), and on a GitHub
   tracker `github_repo` (`<owner>/<repo>`). Both collectors stop on a missing `worktree_mark`.
   The scripts resolve `board_html` against the root they run under.
4. **The hooks**: in `.claude/settings.json`, set `"outputStyle": "Unslop"` and the Stop hook:
   `p=$(cat); python3 ~/.shyrosa/scripts/board.py "$CLAUDE_PROJECT_DIR" < /dev/null && printf '%s' "$p" | python3 ~/.shyrosa/scripts/check-mandatum.py "$CLAUDE_PROJECT_DIR" && printf '%s' "$p" | python3 ~/.shyrosa/scripts/check-tells.py "$CLAUDE_PROJECT_DIR"`
   exactly as written. Claude Code sets `$CLAUDE_PROJECT_DIR` for every hook, so the one line
   names the project on whichever machine runs it. The `p=$(cat)` captures the hook payload once
   so both checks read the same stdin. Merge into an existing `settings.json`; never replace one.
5. **`.claude/board-changed` and the board pair** need no seeding. The first hook run writes
   them. Gitignore all three names (`<project>-board.html`, `<project>-board.md`,
   `.claude/board-changed`): a file that rebuilds every turn cannot live in history.
   **Track the wiring** (`.claude/settings.json`, `.claude/fleet.json`,
   `.claude/output-styles/unslop.md`) so a clone carries it to either machine. If the repo
   gitignores `.claude/`, narrow that to `.claude/*` with a `!` line for each of the three. On a
   public repo, ask the manager before committing them: tracking publishes them.
6. **On a GitHub tracker, create the label strings**: the five triage labels and the four
   `wayfinder:*` labels (`gh label create`). Report which already existed. A configured
   label that is absent from the repo fails the first `gh issue create` that names it.
7. **Name any pre-existing board or queue files in your report and leave them untouched.**
   Reconciling files that hold the same kind of content under other names is the manager's
   decision.

**Pick the file to edit:**

- If `CLAUDE.md` exists, edit it.
- Else if `AGENTS.md` exists, edit it.
- If neither exists, ask the user which one to create; don't pick for them.

Never create `AGENTS.md` when `CLAUDE.md` already exists (or vice versa); always edit the one that's already there.

If an `## Agent skills` block already exists in the chosen file, update its contents in-place rather than appending a duplicate. Don't overwrite user edits to the surrounding sections.

The block:

```markdown
## Agent skills

### Issue tracker

[one-line summary of where issues are tracked]. See `docs/agents/issue-tracker.md`.

### Triage labels

[one-line summary of the label vocabulary]. See `docs/agents/triage-labels.md`.

### Domain docs

[one-line summary of layout: "single-context" or "multi-context"]. See `docs/agents/domain.md`.

### Ticket naming and sources

Every ticket has a fixed handle and says which door it came through. Use these names when writing to the user. See `docs/agents/tickets-naming-and-sources.md`.

### Parking queues

Park a question the moment it surfaces rather than carrying it to the end of the session. See `docs/agents/queues.md`.

### Parallel implementation

When `ready-for-agent` tickets are waiting, e.g. right after `/to-tickets` publishes, offer to fan out: one worker pane per ticket via the `tmux-orchestrator` skill, dispatch loop in `docs/agents/fan-out.md`.
```

Include the `### Triage labels` sub-block, and write `docs/agents/triage-labels.md`, only when `triage` is installed and Section B ran. When it isn't, both are omitted.

Then write the docs files using the seed templates in this skill folder as a starting point:

- [issue-tracker-github.md](./issue-tracker-github.md): GitHub issue tracker
- [issue-tracker-gitlab.md](./issue-tracker-gitlab.md): GitLab issue tracker
- [issue-tracker-local.md](./issue-tracker-local.md): local-markdown issue tracker
- [triage-labels.md](./triage-labels.md): label mapping (only if `triage` is installed)
- [domain.md](./domain.md): domain doc consumer rules + layout
- [tickets-naming-and-sources.md](./tickets-naming-and-sources.md): ticket handles, the `Source:` chain, and the doors that file tickets. Always written. Also **create `<tracker-root>/GRILL-LOG.md`** with its heading and an empty table. It issues the `g<NN>` numbers that name threads, and the project's first grill takes `g01`
- [queues.md](./queues.md): where a question parks when it surfaces mid-work. Always written; **fill in the path** where this repo's live pair will sit. Keep the **studio queue** bullet only when `commission-design` is installed (a `commission-design` folder in `~/.claude/skills/`); without it the grill queue stands alone
- [fan-out.md](./fan-out.md): parallel implementation dispatch loop. Requires the `tmux-orchestrator` skill (a `tmux-orchestrator` folder in `~/.claude/skills/`). If it's absent, skip this file AND omit the "Parallel implementation" subsection from the block.

For "other" issue trackers, write `docs/agents/issue-tracker.md` from scratch using the user's description.

### 5. Done

Tell the user the setup is complete and which engineering skills will now read from these files. Mention they can edit `docs/agents/*.md` directly later; those files hold **this repo's configuration only**; a rule that would bind any project belongs in `~/.shyrosa/WORKFLOW-RULEBOOK.md`, never here. Re-running this skill is safe: it repairs, adds what is missing, overwrites nothing, and reports what it added.
