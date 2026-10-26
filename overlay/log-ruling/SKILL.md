---
name: log-ruling
description: Record a settled workflow ruling: the reasoning into the ledger, the line that binds into the rulebook, any new word into the vocab. Invoke right after the ruling, in the same session.
disable-model-invocation: true
hide: true
---

# Log Ruling

You just settled how the flow works. Write it down so nobody re-asks it, and put each part where
its reader will actually meet it.

## Three files, three jobs

A ruling splits three ways. Writing all of it into one file is the failure this skill exists to
prevent: reasoning buries the rule, and the rule reaches nobody.

| File | Holds | Shape |
|---|---|---|
| `LEDGER.md`, beside this skill | **why** it binds: question, verdict, date | append-only, newest wins |
| `~/.shyrosa/WORKFLOW-RULEBOOK.md` | **what** binds an agent today | live only, undated, grouped by activity |
| `~/.shyrosa/WORKFLOW-VOCAB.md` | the fleet's **words** | one definition per word, once |

**The rulebook is the reach.** Every project's `CLAUDE.md` points at it by path, so a rule written
there lands in every project at its next session start. A ruling that stops at the ledger binds
nobody: the ledger sits inside this hidden skill, which no director or worker loads.

## Steps

1. **Name the ruling.** From what was just discussed in this session, state the settled
   question in one line and the verdict in a few. **Stop here when nothing was settled.** A "which
   skill fits?" lookup the router already answers is not a ruling, and logging it is noise.

2. **Write the why.** Append to `LEDGER.md`, under the section the ruling belongs to (the master
   flow, the per-ticket build loop, boundaries, standing constraints…). Match the file's live shape:

   ```
   **Q (YYYY-MM-DD):** <the question, in your words>

   **Ruling: <the verdict in a few words>.** <why it went that way, in the flow's own vocabulary>
   ```

   Open a new section only when no existing one fits.

3. **Write what binds.** Add or amend the rule in `WORKFLOW-RULEBOOK.md`, in the section named for
   what an agent is *doing* when it needs the rule. Follow that file's own shape exactly: a bold
   lead, the rule, an audience tag, and the ledger section it came from, like `**(D)** — §7`.

   State the rule, never its history. The rulebook holds today's answer; the date and the reasoning
   are the ledger's job.

4. **Name any new word.** A ruling that coins a word adds it to `WORKFLOW-VOCAB.md`, in the section
   it belongs to. A word naming a **thing** carries its whole meaning there; a word naming a
   **procedure** carries its meaning and then names the file holding the steps.

5. **Supersede.** When this ruling replaces an earlier one, mark the old ledger entry
   `~~superseded YYYY-MM-DD~~` with a one-line pointer to the new one, and edit the rulebook line so
   exactly one live answer stands. The ledger keeps both; the rulebook keeps one.

6. **Route a project-only rule to that project.** The test is whether a second project would need
   it. Yes → the rulebook. No → that project's own `CLAUDE.md` or `docs/agents/*.md`. Tracker
   paths, port numbers and repo layout are project-only; everything about how agents work together
   is fleet.

**Done when:** the reasoning sits in the ledger under its section and date, the binding line sits in
the rulebook with an audience tag and a ledger citation, any coined word sits in the vocab, and
every entry this ruling replaces is marked superseded.
