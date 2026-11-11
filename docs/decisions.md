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

**Update 2026-11-11 (in class).** The instructor said several teams may take the same use case, so R1's
"no two teams share a use case" no longer applies. The ranking stands on merit alone (merit order:
UC3 > UC5 > UC7 > UC1 > UC4 > UC2 > UC6 > UC8). A unique use case also avoids being compared on the same hidden
test cases with teams that started a week earlier.

**Alternatives considered.** UC1 > UC2 > UC6 (a teammate's suggestion): UC1 and UC2 are contested, so it would
in practice assign us UC6, whose multilingual hidden cases and dated travel rules add risk. UC8: hardest data and
near-identical HS codes in hidden tests.

## D-001 — The repository is the team's single source of truth (accepted, 2026-11-11)

**Decision.** Requirements (`docs/course/requirements.md`), current status (`docs/STATUS.md`) and decisions (this
file) live in the repo next to the code, not in chats or private notes.

**Why.** Everyone sees the same version, changes are reviewed and dated, and the history doubles as evidence for
the contributions section of the weekly report.

**Consequence.** A decision made in a meeting or a chat counts only once it is written here.
