# Decisions

One entry per decision that someone could later ask "why?" about. Newest first. Status: proposed, accepted,
superseded (keep superseded entries; link the replacement).

## D-001 — The repository is the shared state between people and AI tools (accepted, 2026-11-11)

**Decision.** Requirements, status, decisions and work requests live in this repo (`docs/`). The claude.ai
planning chat writes work requests to `docs/handoffs/`; Claude Code implements them and writes the Result.

**Why.** Claude Code cannot see the claude.ai project's files or chats, and teammates may use other tools.
A file in git is visible to everyone, versioned, and is itself evidence for the contributions and AI-tools
sections of the weekly report (R15).

**Consequence.** Anything a coding agent needs from the handbook or a planning discussion must be written into
the repo; chat-only decisions don't count.
