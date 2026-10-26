---
name: relieve-and-handoff
description: Relieve an agent whose context is filling up, handing its work to a fresh one in the same window. Use when a worker or director is running out of room, or before sending more work into an agent that is already half full.
---

# Relieving an agent

Relief is the **foreman's** duty, at every level below the manager: the foreman relieves directors and workers both, and the manager relieves the foreman (his ruling, g04, 2026-08-16). A director relieves nobody. **Worker relief is inform-only:** send the project's director one line. Name the pane, the ticket, and that you are relieving now. Then act without waiting; a mistimed relief is cheap by design, so a permission round-trip buys nothing. If you are not the foreman and a session is filling, the agent needing relief is you or yours: say so to whoever watches you, and stop. Judging your own state is the one judgement that fails exactly when it is needed.

An agent between jobs, holding nothing worth carrying, needs no handoff. Quit it and relaunch on the next task (`tmux-orchestrator`). Relief is for an agent whose context **is** the valuable thing: mid-work, or sitting at a gate for a fix round only it can do well.

## When

Read the agent's context fill from its transcript. A question put into its window spends the very thing you are trying to save, so judge from outside: on its latest assistant turn, sum `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` and divide by the window of the model it is running.

```
50%     start watching — reading costs the watched agent nothing
50–70%  relieve it the moment it is calm
70%     ask it to calm down, if what it holds can be written down;
        if it cannot, keep watching
80%     ask regardless, and accept what the document loses
```

**A calm agent above 50% is relieved, not loaded.** Sending it one more ticket is what puts it over mid-work later, and mid-work is the expensive kind of relief. The moment you would have dispatched is the moment to relieve, and relief is the manager's preference over letting the session auto-compact: a handoff writes down what matters, where compaction decides for itself what to keep (*"i prefer handoff over compact"*, 2026-08-02).

## The two tests

**Is it calm?** All three hold:

1. nothing is running,
2. nothing is half-finished,
3. nothing that matters lives only in its head.

**Can it be made calm?** Could it write down what it holds in a sentence or two? A half-made edit, or a finding in its head, is writable, so asking works. A hypothesis it cannot articulate yet is not, so asking buys a vague note and a lost thread. Wait for the hypothesis to become a finding, which *is* writable.

## The routine

1. **Ask for calm**, when it is not calm already. Send: *"You are about to be handed off. Finish only what would be lost or left broken if you stopped right now. Leave everything else for the next agent."* It judges what cannot wait. That judgement is its own. *Done when* its transcript shows all three conditions hold.
2. **Send `/handoff`** into its pane. *Done when* the document exists.
3. **Split its window** and start the fresh agent there, told to read the document at its path. The commands are `tmux-orchestrator`'s, under *Relieving an agent in place*. *Done when* an agent is running in the new pane.

   **The name says what the pane is, so relief renames it only when that changed.** A worker's name is its ticket, and relief swaps who is building it, not which ticket it is. So the ticket handle is fixed across the relief, and the successor launches under that handle with an index appended after a dot: the second agent on the ticket is `<handle>.2`, the third `.3`, the fourth `.4`. Work the index out by counting the sessions already answering to that handle, so nothing stores a counter and nothing has to be remembered between reliefs. This is the one statement of the rule; anywhere else that needs it points here, and the glossary's `handle` entry gives how the indexed handle reads in a pane's `-n`. A director is the other case, a separate rule: its name is its own number, so the successor takes the next one, and the document names both ends (`director-22-to-23-handoff.md`; the naming rule lives in the `handoff` skill). The window's own name and index are untouched either way.

   **Launch settings are copied from the spent session: model, effort, and permission mode, exactly as the outgoing agent ran them** (his rule, 2026-08-15; the mode joined it in g10, 2026-08-17). Read model and effort from the transcript or the pane's status line; read the permission mode from the transcript alone: its **last** `permission-mode` entry is the mode actually running, and the status line does not render it. The copy is the whole decision: nothing comes from the agent's role, and nothing is stored. When the manager states a different mode at a relief, his word sets that successor, and the next relief copies whatever then runs.
4. **Verify the handover.** *Done when* the fresh agent names the work it is picking up.
5. **Quit the spent agent with `/exit`, then kill its pane** (same section). Killing the pane alone leaves its session running unseen. *Done when* one pane remains and the spent session has quit.

Those three in that order are what lets you verify before you destroy: the predecessor is alive until the successor has proven it read the document.

**Done when** the fresh agent holds the work and the spent pane is gone.
