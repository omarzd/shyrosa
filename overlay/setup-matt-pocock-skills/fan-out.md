# Parallel implementation: this project's dispatch facts

The dispatch policy is the fleet's, in `~/.shyrosa/WORKFLOW-RULEBOOK.md` (*Building*, *Reviewing
and merging*, *Panes and dispatch*): one worker one ticket, the gate, escalate-don't-loop, who
says the merge word. Pane mechanics are the `tmux-orchestrator` skill's job: discovering panes,
verified send, waiting, reading replies via transcripts, recycling a worker. Invoke it and
follow it. This file holds only what is true of this repo alone.

- **The dispatch prompt**: send each idle worker `/implement <ticket-ref>`, plus the spec
  reference when one exists. [Fill in when this repo grows its own dispatch recipe, ports to
  avoid, or gate commands beyond suite-and-typecheck. Delete this line if it never does.]
