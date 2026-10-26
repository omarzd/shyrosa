# Tickets: naming and sources

What every item in the tracker is called, and where it came from. Use these names in anything the
manager reads. A name invented for one message costs him the ability to refer to the thing later.

## What exists

```
project
└── thread            .scratch/g<NN>-<slug>/     one grill, one thread
    ├── spec          spec.md                    the grill's residue; one per thread
    ├── grill notes   GRILL-NOTES*.md            the trail
    └── tickets       issues/<NN>-<slug>.md      the leaves — all work lives here
```

Tickets are **leaves**: atomic, each demoable and mergeable alone. They relate to each other only
through `Blocked by:`, never as parent and child. There are no epics. The only parents are the
thread and its spec.

Two files sit at the project root and outlive every thread: `GRILL-QUEUE.md` and `STUDIO-QUEUE.md`
(see [queues.md](./queues.md)), plus `GRILL-LOG.md`, which issues grill numbers.

## Handles: how to name a thing

| Thing | Handle | Example |
|---|---|---|
| Thread | its folder slug | `g14-checkout` |
| Spec | the thread's handle, since a spec has no separate name | `the g14-checkout spec` |
| Ticket | `<thread>/<NN> <slug>` | `g14-checkout/07 guest-address-reuse` |
| Grill | its number, from `GRILL-LOG.md` | `g14` |

Inside a conversation already about one thread, `07 guest-address-reuse` is enough. Everywhere else,
lead with the thread.

**A ticket's handle is fixed at birth and never changes**: not when its status moves, not when it
is deferred, not when it turns out to be something else. The filename carries no status, so nothing
has to be renamed and no reference to it can break.

## Sources: how a ticket says where it came from

A line in every ticket, directly beneath its `Status:` line:

```
Source: <parent handle> -> <door> [<date>]
```

A chain, read left to right: what it came out of, then what turned it up. The date disambiguates
doors that fire repeatedly against the same parent.

**The doors and their closed list live in `~/.shyrosa/WORKFLOW-RULEBOOK.md` (*Tickets*)**. One
fleet list, since 2026-08-13; three projects had drifted to three different tables.

```
Source: g14-checkout -> to-tickets
Source: g14-checkout -> manager-conversation 2026-08-02
Source: g11-billing/05 -> code-review
Source: g11-billing/05 -> merge-gate 2026-08-01
Source: g11-billing -> director-sweep 2026-07-27
Source: g14-checkout -> studio C5b
Source: director-sweep 2026-07-27
```

The parent is a **ticket** when a ticket was the thing under review, otherwise the **thread**. A
sweep that belongs to no thread is a chain of one.

**Source records where the item was found, not where it belongs.** A sweep running under one thread
that catches a defect in another files the ticket in the *other* thread's folder, taking that
thread's next number, while its `Source` still names the sweep that found it. Location says whose
work it is; `Source` says what turned it up.

**A door joins the fleet list only at the manager's word.** A director that needs a missing one
files the need as `needs-triage` and files nothing through it meanwhile (his ruling, 2026-08-13,
replacing this file's old "add it here first").
`/wayfinder` and `/diagnosing-bugs` can both file work and have not yet; they join the table on the
day they do.

## Ticket birth rules

Three rules, all applied at the moment the file is created, by whichever door creates it:

1. **Number**: the next free number in that thread's `issues/` folder. Every door shares one
   sequence per thread. Within a `to-tickets` batch the numbers still read blockers-first; a ticket
   filed later is simply the next one along, and its dependencies live in `Blocked by:` as always.
2. **Source**: the chain above, beneath the `Status:` line.
3. **Status**: the `Status:` line is where status lives, so the filename never carries it.

## Grill numbers

`GRILL-LOG.md` at the project root registers every grill at the moment it opens, whichever grill
skill runs it, including grills that end with nothing to build. Its number founds the thread and
never changes. A re-grill of the same topic logs a new grill against the existing thread rather
than renumbering it.
