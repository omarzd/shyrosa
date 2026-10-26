---
name: route-after-grill
description: Runs at a grill's close, called by the grill-me and grill-with-docs overlays. Decides, from lists rather than judgment, whether the close advises /implement here, /to-spec, or nothing to build.
hide: true
---

The grill just declared its frontier empty. You were called by the close of `/grill-me` or
`/grill-with-docs`; do not build anything and do not invoke any further skill. Produce the three
lists below in order, then apply the routing rule and print the exit. **Enumerate before you
judge**: the verdict must fall out of the lists; never state it first.

## 1. Deliverables

List every **deliverable** the feature produces. A deliverable is something the user could see
working on its own: a screen renders, a command runs, a calculation returns the right number
for a named test case. It must **also** be something that could be committed and merged alone
without breaking the app. If you are unsure whether something is one deliverable or two, count two.

Done when: nothing decided in the grill is missing from the list, and each entry passes both
tests (demoable alone, mergeable alone).

## 2. Footprint

Under each deliverable, list the files or modules it creates or edits: real repo paths where
code already exists, a named target folder where it would be new.

Done when: every deliverable has its paths; no entry says "various" or "TBD".

## 3. Build-dependent questions

List every question this grill answered with "we'll find out when we build it": any decision
that depends on running code that does not exist yet. Quote the moment from the conversation.

Done when: the list is explicit, even if empty ("none").

## 4. Route

Apply mechanically. No judgment enters here. A grill thread is named `g<NN>-<slug>` (see
`WORKFLOW-VOCAB.md`); the `<thread>` an exit prints is its grill number alone, the `g29` of a
`g29-<slug>` thread, not the slugged name, the same shape the rulebook uses in `/implement g20`
and `/log-ruling g14`.

- **Zero deliverables** → verdict `NOTHING TO BUILD`. The grill settled thinking, not work. If a
  workflow ruling landed in it, the exit is `/log-ruling <thread>` so the ruling reaches the
  ledger, the rulebook and the vocab. If nothing was settled to record, there is no exit line and
  no `## MANDATUM` section.
- **Exactly one deliverable and zero build-dependent questions** → verdict `SINGLE SESSION`. Two
  exits sit side by side: `/implement <thread>` builds it inline in this same window, and
  `/to-spec <thread>` formalizes it into one spec and one ticket for a worker to build. The
  dispatch `CONFIRM` follows `/to-spec`, not this close, because a worker builds one ticket and the
  dispatch is its own step. Print both lines; the manager picks one by typing it.
- **Two or more deliverables, or any build-dependent question** → verdict `MULTIPLE SESSIONS`. The
  exit is `/to-spec <thread>`, which synthesizes the thread into a spec published to the tracker.
  Everything after it, `/grill-spec` when asked, `/to-tickets`, one ticket per deliverable, the
  fan-out, and any `/prototype` detour bridged by `/handoff` for a build-dependent question, comes
  to the manager as its own line at its own close. This exit names only the next step.

Print the verdict, the deliverable count, and the exit line or lines. The exit is the
`## MANDATUM` section's only content: a copy-pasteable `<command> <args>` line the manager types,
nothing after it. Typing the exit is the manager's word that the lists hold and the close was
right; a "not yet" discards the lists, and they run again at the next close. You advise; the
manager invokes.
