# Rebuilding a handoff that has gone missing

A missing handoff is a missing document, not lost work: **session transcripts are durable.** They live at `~/.claude/projects/<project-slug>/*.jsonl`, one file per session, where the slug is the project's absolute path with each `/` written as `-`.

Two routes back:

- **Resume the session and ask it again.** `claude --resume` opens a picker, which a search term filters and a session id skips. Once inside, invoke `handoff`.
- **Read the transcript directly**, when the session is long finished. List candidates by time (`ls -t`), then confirm you have the right one by grepping for work the handoff was meant to describe.

Read the transcript **whole** before writing. A handoff carries which pane holds which ticket, and which decision settled and why. That is established early and referred to obliquely afterwards, so a tail read yields a confident document about the last ten minutes of a session. Rebuild what the transcript shows, and name the gaps.
