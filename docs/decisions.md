# Decisions

One entry per decision that someone could later ask "why?" about. Newest first. Status: proposed, accepted,
superseded (keep superseded entries; link the replacement).

## D-002 — Use case preference: UC3 > UC5 > UC7 (accepted, 2026-11-11; assignment pending)

**Decision.** Rank UC3 (property management) first, UC5 (HR helpdesk) second, UC7 (IT helpdesk) third.

**Why.** Grade levers that differ between use cases are the hidden test set (10%) and red-team defense (5%).
UC3 and UC5 have exact expected end states and an access-control problem we can enforce in code (identity from
the session, tools return only that user's data), so attacks fail structurally rather than depending on the
model. Synthetic data is quick to write, leaving time for experiments. Class survey on 2026-11-11 (public repos):
UC1 wanted first by three teams, UC4 by one; nobody ranked UC3 or UC5 first. UC7 is our best remaining option on
merit even though other teams list it second.

**Alternatives considered.** UC1 > UC2 > UC6 (a teammate's suggestion): UC1 and UC2 are contested, so it would
in practice assign us UC6, whose multilingual hidden cases and dated travel rules add risk. UC8: hardest data and
near-identical HS codes in hidden tests.

## D-001 — The repository is the shared state between people and AI tools (accepted, 2026-11-11)

**Decision.** Requirements, status, decisions and work requests live in this repo (`docs/`). The claude.ai
planning chat writes work requests to `docs/handoffs/`; Claude Code implements them and writes the Result.

**Why.** Claude Code cannot see the claude.ai project's files or chats, and teammates may use other tools.
A file in git is visible to everyone, versioned, and is itself evidence for the contributions and AI-tools
sections of the weekly report (R15).

**Consequence.** Anything a coding agent needs from the handbook or a planning discussion must be written into
the repo; chat-only decisions don't count.
