# Decisions

One entry per decision that someone could later ask "why?" about. Newest first. Status: proposed, accepted,
superseded (keep superseded entries; link the replacement).

## D-006 — Model: gpt-oss-120b on Groq's free plan (accepted, 2026-11-16; owner: evaluation and safety lead)

**Decision.** Main model `openai/gpt-oss-120b` via Groq's OpenAI-compatible endpoint, free plan. Backup and later
judge: `qwen/qwen3.8-27b` (a different model family, so the judge does not grade its own family). Teammates may
object until week 2.

**Why.** Gemini on the AI Studio free tier was the first choice. Rejected on evidence: the AI Studio rate-limit page
on 2026-11-16 showed 20 requests per day for Gemini 3.8 Flash, 2.5 Flash and 2.5 Flash Lite, and 0 for the other
models. The week-1 baseline alone needs 75 calls (25 inputs × 3 temperatures); W6.3 needs every task run 5×.
Groq console limits for gpt-oss-120b on 2026-11-16: 30 RPM, 1K RPD, 8K TPM, 200K TPD.

**Consequences.** The binding limit is 8K tokens per minute, so runs are paced with `--sleep`. gpt-oss is a
reasoning model, so hidden reasoning tokens count toward cost and limits. A manual smoke test pointed this out
before the baseline; it is not a committed result, and the measured numbers are in W1.6 (`docs/cost_estimate.md`). Each member uses their own key; experiments that are
compared run on one key and one model id, never an alias.

## D-005 — Response to the RAG feedback (proposed, 2026-11-16; owner: data and retrieval lead)

**Context.** At the proposal (2026-11-11) the instructor found our RAG design insufficient. We did not record his
exact words; we confirm our reading in the week-1 presentation.

**Our reading of the gaps (from proposal slide 4).** (1) 28 documents, below W3.1's minimum of 30. (2) Retrieval
too easy: one syllabus per course, so a course code in the query already identifies the document; hit@k would sit
near the ceiling and W3.7 ablations would show nothing. (3) RAG sits beside the core (extraction) instead of inside
it. (4) No "who may see it" metadata, which W3.1 requires.

**Proposal.** Use retrieval inside extraction: when a message changes or refers to a date it does not state
("HW3 is extended by one week", "before the make-up week"), retrieve the original syllabus, announcement or
calendar passage, compute the new date in code and cite both sources. Build a deliberately harder corpus of
45–60 documents: revised syllabus versions, confusable course codes, the regulation split by article, the
academic calendar, course policies that override the regulation. Metadata per chunk: course, doc type, version,
valid from, language, audience.

**Detail (2026-11-17).** The corpus will consist of 48 documents, distributed by type as detailed in the table in `docs/data_inventory.md` §1. To ensure precise citations with article or heading numbers, `doc_id` and `section` fields have been added to the per-chunk metadata, which were missing from the original list. The corpus will contain the 8 facts required for the test inputs' expected answers, corresponding to the "Facts" table in the inventory. Dormitory and tuition fee documents will be excluded, as noted in the "Deliberately not in the corpus" row, so that input w1-20 deliberately remains unanswerable.

**Open.** Storage and search stack: the proposal slide said PostgreSQL with pgvector; for a corpus this size BM25
plus in-memory embeddings may be enough. Decide with the agent and tools lead and record the reason here. The stack question has been directed to Enes and will be resolved in week 2, before the RAG work starts in week 3.

## D-004 — Scope A, payer kept as a hypothesis (accepted, 2026-11-16)

**Decision.** Scope A from the proposal: messages → verified deadlines is the core; rule Q&A with citations
supports it. Who pays stays a hypothesis (an LMS add-on, proposal slide 8) until the week-5 pricing task.

**Why.** The instructor left both choices to us. A differs most from the lecture example, and with D-005 it also
puts retrieval inside the core. Scope B would make RAG the core but is the closest to the lecture example; C
carries the most risk in seven weeks.

**Update 2026-11-17 (payer).** The use case brief (W1.2) names the university itself as the payer: the LMS is the
school's own system, so there is no LMS vendor to sell an add-on to. This replaces the LMS add-on hypothesis. Who
pays is still a hypothesis until the week-5 pricing task.

## D-003 — Product: Deadline Radar, our own idea (accepted, 2026-11-11; supersedes D-002)

**Decision.** Build Deadline Radar instead of a handbook use case: one verified deadline list from emails, LMS
posts and syllabi, plus cited answers to school-rule questions. First user: an undergraduate taking 4–6 courses.

**Why.** The instructor allows ideas outside the eight use cases and accepted this one at the proposal on
2026-11-11 (`docs/proposal/`). It contains all eight handbook ingredients, and we are its users, so we can write
realistic inputs and judge the answers.

**Consequence.** D-002 is superseded. The hidden test cases (10 % of the grade) will be written for our product,
so the input and output formats we define in week 1 matter beyond week 1.

## D-002 — Use case preference: UC3 > UC5 > UC7 (superseded by D-003, 2026-11-11)

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
