---
name: grill-spec
description: An independent red-team of a finished spec that grills its gaps before it becomes tickets.
disable-model-invocation: true
hide: true
---

Run a `/grilling` session as an independent red-team of a spec that already exists, before it is split into tickets.

You did not write this spec. Read only the spec, `GLOSSARY.md`, and the ADRs, not the original grill thread; a red-team works from fresh eyes.

Start from a clean working tree: if uncommitted changes are sitting in the repo, have them committed before you begin, so the diff you leave is exactly yours.

First red-team the spec into a prioritised list of what will bite during the build:

- **Gaps**: states, cases, or failure paths the spec never says what to do about.
- **Ambiguities**: anything a builder could read two ways.
- **Unsound seams**: an interface, coupling, or ordering the spec assumes but does not hold.
- **Domain conflicts**: anything that contradicts `GLOSSARY.md` or an ADR (domain wins).
- **Untestable criteria**: an acceptance criterion no test could decide pass or fail on.
- **Mis-scope**: one "deliverable" that is really two, or a build-dependent unknown posing as decided.
- **Enumerated universals**: a rule that binds everywhere, written as the list of places it applies. The list is always short by one, so every review finds the same defect class somewhere it does not name, and each round fixes one more instance. State the rule and let the check find the places.

Then grill me through the highest-leverage findings. Land each one in the workflow's existing vocabulary: a **spec edit** when it is settled here and now, a **needs-triage** item when it is work for later, the **grill queue** when it is a domain question that needs a grill of its own. Every finding lands in exactly one of those three, including the ones you defer. A ticket you file takes the thread's next free number and carries `Source: <thread> -> grill-spec` beneath its `Status:`. See `docs/agents/tickets-naming-and-sources.md`. When a resolution settles a domain rule, record it in `GLOSSARY.md` or an ADR via `/domain-modeling`, not just the spec.

Commit your edits, with messages that say they came from the spec consultant. The review that follows reads your commits, not a memory of the files.

Done when every high-leverage finding has landed in one of the three destinations above, the spec has zero build-dependent unknowns left, your edits are committed, and the hand-back names where each deferral lives. Zero unknowns is the state `/route-after-grill` needs to split it.

Close with a block the user pastes into the director's session. **Point, don't copy:** name the commits to review, where the spec stands, and, for each finding you deferred, the file or section now holding it, so the director reads your commits rather than treating pasted prose as a second source. Length is whatever that takes.

> `Spec consultant finished: review commits <spec-sha> (spec), <domain-sha> (GLOSSARY §N), <triage-sha> (triage item). <spec-path> has zero build-dependent unknowns. Every deferral is recorded in those commits: <item> = needs-triage item <filename>; <item> = grill queue entry "<title>"; <item> = GLOSSARY §N. Nothing promoted to ready-for-agent.`

You never write a `## MANDATUM` section. That block is your session's last message; nothing follows it, and the manager's paste into the director's window is the next move.
