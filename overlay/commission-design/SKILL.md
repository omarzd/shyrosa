---
name: commission-design
description: Commission screen designs between /to-spec and /to-tickets (or before an inline /implement). Briefs pushed to a persistent claude.ai/design studio that grills you on look and returns handoffs, reconciled against the domain model, design contracts into the tickets.
disable-model-invocation: true
hide: true
---

# Commission Design

Sits between `/to-spec` and `/to-tickets` (multi-session), or between `/grill-with-docs` and an inline `/implement` (single-session). It exists to move design **upstream of the tickets**, so implementation builds against a design that already exists instead of retrofitting one after the fact.

Five leading words carry the skill:

- **brief**: a self-contained commission for one screen. It is the *only* thing you author for design; domain and design never share a thread.
- **studio**: your persistent design home on **claude.ai/design**, a `DESIGN_SYSTEM` project that *grows per commission*. The design system lives here. The studio owns *look*. You reach it by name under your claude.ai login, and the design agent both **works and grills you** in it.
- **handoff**: what the studio returns for a screen. A high-fidelity reference (`README` + self-contained HTML + light/dark/RTL screenshots) to be *recreated* in the codebase, not shipped as-is.
- **archetype**: every screen is one of a few archetypes (an airy *summary* screen vs a dense *table* screen). One design system, extrapolated from a small set of **anchor** screens. You do not commission every screen.
- **reconcile**: the **studio** is authoritative for *look*; `GLOSSARY.md` is authoritative for *meaning and labels*. Where a handoff's concept disagrees with the domain, the domain wins.

This skill does **not** grill you itself. It plants a grill-instruction in the **studio** and the **studio grills you** on look. You carry the interrogation as *content*, not as a local step. Never route a handoff back through the grill thread. Design lives in the studio and in `docs/design/` (its reconciled local mirror), never in the domain conversation.

**Transport is `/design-sync`.** Every push/pull between your repo and the studio goes through the connector-managed `/design-sync` skill (the `DesignSync` tool), one component at a time, never a wholesale replace. This skill decides *what* to sync and *when*; `/design-sync` moves the bytes. Prerequisite: `/design consent` once per environment.

## Process

### 1. Gather

Read the design-system ADR and every existing `handoff` under `docs/design/` (their tokens, typography, RTL rules), the spec (or the current conversation, single-session), and `GLOSSARY.md` for domain labels. Confirm the **studio** exists. `/design-sync` → `list_projects`. If none is there, this is a **first run**: there is no design system yet, and the studio you create in step 5 will *define* it.

Completion: you know the studio's identity (or that this is a first run), the existing design-system rules, and the domain labels.

### 2. Enumerate screens

List **every** screen the plan implies. Tag each with its **archetype**, and mark its state:

- **has handoff**: already designed in the studio; skip.
- **extrapolate**: a new screen of an existing archetype, close enough to an existing **anchor** to build without a fresh brief.
- **needs brief**: a new archetype, or a screen distinctive enough to commission.

On a first run, the needs-brief set is one **summary** anchor plus one or two dense **anchors**; every other screen extrapolates from those.

Completion: every implied screen is listed, archetype-tagged, and in exactly one of the three states.

### 3. Quiz the user

Present the screen list as a numbered table (screen · archetype · state). Ask whether the archetypes and the has-handoff / extrapolate / needs-brief split are right. Iterate until approved. (This is the local *screen-list* quiz, distinct from the studio's look-grill in step 5.)

### 4. Write a brief per needs-brief screen

Write each **brief** to `docs/design/briefs/`, matching the depth of any existing brief. Each is self-contained. The studio reads only the brief. Its first five fields carry the **domain** side (*copied* from `GLOSSARY.md`/ADRs, already settled, not grilled); its last field carries the **grill-instruction** that makes the studio interrogate you on the *look* side before it designs:

<brief-skeleton>
# Design brief for <archetype>: <screen name>

## What this screen is: role, who sees it, what question it answers
## Ethos: the feeling; unchanged from the design system
## Content: every element, using GLOSSARY.md's exact labels
## Hard constraints: tokens / typography / RTL / number+date rules copied VERBATIM from the design system (on a first run, this section *defines* them)
## Deliverable: a handoff in the established format (README + self-contained HTML + light/dark/AR-RTL screenshots), to be recreated in the codebase, not shipped
## Interrogate me: "Before you design anything, grill me one question at a time on the look-side dimensions a brief can't fix: visual hierarchy, interaction states, empty/error/loading, responsive behaviour, RTL, accessibility, archetype fit. Do NOT produce the handoff until you've walked the whole tree."
</brief-skeleton>

This is the **reconcile** seam applied to *when* you grill: the domain is locked locally so the studio can't get labels wrong; the look is interrogated in the studio, where the design skills actually live.

Completion: every needs-brief screen from step 2 has a brief, including its Interrogate-me block.

### 5. Commission in the studio

Push each brief up to the studio via `/design-sync`. On a **first run**, `/design-sync` first creates the studio (`create_project`, named recognizably, e.g. `<repo> — design system`). Then open the studio in claude.ai/design (find it by name under your login) and say go: it **grills you** per the brief's Interrogate-me block, designs the screen consistent with the design system already living in the studio, and leaves the `handoff` there. You do not run the design agent yourself. The studio does. On a first run, the handoff *defines* the tokens / typography / RTL rules; record them afterward as a design-system ADR so later runs reuse them.

Completion: every brief from step 4 has its handoff in the studio.

### 6. Reconcile: pull down, domain wins, push corrections back

Pull the studio down via `/design-sync` into `docs/design/<screen>/`. For each new handoff, check **every** visible label against `GLOSSARY.md`. Where a label names a domain concept differently, the **domain wins**. Correct it locally, and note the correction. Flag any handoff element with no domain backing. Then **push the corrections back up** to the studio via `/design-sync`, so the living design system stops re-emitting the wrong label next commission. Record notable deltas in the design-system ADR.

`docs/design/` is the reconciled **mirror**, never a source: look-changes originate in the studio, label-changes originate from `GLOSSARY.md` and flow up. Never hand-edit the design system in the repo.

Completion: every handoff label is checked, every mismatch corrected both in `docs/design/` and pushed back to the studio.

### 7. Emit design contracts

**Multi-session** (tickets follow). Specify a **design-system-foundation** slice for `/to-tickets` to publish first: it extracts the handoffs' tokens, fonts, RTL infra, and core components into the codebase, and every visual slice blocks on it. Do NOT publish tickets yourself. Only `/to-tickets` publishes. Then, for each visual screen, produce a **design contract** for `/to-tickets` to paste into the ticket body:

<design-contract>
## Design
Handoff: `docs/design/<screen>/` · system: `<design-system ADR>`

## Blocked by
<design-system-foundation ticket>
</design-contract>

Completion: the foundation slice is specified and every visual screen has a design contract.

**Single-session** (no tickets). Hand the reconciled handoffs straight to `/implement` in this thread; the design contract is just the handoff path already in context.
