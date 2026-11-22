# Decisions

One entry per decision that someone could later ask "why?" about. Newest first. Status: proposed, accepted,
superseded (keep superseded entries; link the replacement).

## D-009 — Evaluation rules: keep measuring apart from building (accepted, 2026-11-22; proposed 2026-11-21; owner: evaluation and safety lead)

**Context.** A review of weeks 2–3 on 2026-11-21 found six gaps. None is anyone's fault; each would make a
reported number weaker than it looks.

| # | What happened | Why it matters |
|---|---|---|
| 1 | The 17 `new` cases were committed on 19 Nov 20:57; `prompts/extract_v1.md` and `dates.py` were written after them and contain their wording (w2-04 "ara rapor", w2-08 `termpaper`, w2-09 "haftaya") | The `new` split no longer measures unseen inputs, so it cannot predict the hidden test set (10%) |
| 2 | Three prompt versions are due Sat 21 14:00, but which prompt is compared and what each version changes is written nowhere | A result explained after the run is not evidence; several changes per version make the cause unknowable |
| 3 | Week-2 runs will use `search_stub` and a deadline table seeded with expected rows | Without saying so, the accuracy reads as the real system's |
| 4 | The rule for `ask_user` changed in `tools/deadlines.py`, while `eval/testsets/README.md` still gave the old rule until `5a10169` | New cases get labelled by the wrong rule; two answers to the same question in a presentation |
| 5 | The classifier returns `urgency`, which no case grades | A field nobody measures is either unproven or unneeded |
| 6 | Three Friday deadlines in `docs/STATUS.md` (rows 4, 5 and 6) passed without a message to the team | The plan for weeks 2–3 learns about a delay a day late |

**Decision.** These rules add to `CONTRIBUTING.md` (one change per experiment, frozen test sets, result files
record their commit); they do not repeat it.

1. **Held-out cases are written and run by the evaluation and safety lead only.** Whoever writes prompts or
   pipeline code does not read them. Until their numbers are first reported, only the file's sha256, n and type
   counts are committed (this proves the file did not change later); the file itself is committed at the tag
   where its numbers are first reported (R8), and from then on it is development data. The next held-out set gets
   a new version. Prompt authors see the aggregate score and, after their version is final, the failed case ids.
2. **Plan before you run.** Before a comparison, its row goes into the Experiments table of `docs/STATUS.md` with
   hypothesis, the one change, the test set, and the number that decides. The result and the decision are added
   after the run; the plan is not rewritten.
3. **Every number carries its conditions.** The harness writes them to `config.json`: commit, prompt versions,
   model, temperature, test set path and sha256, search backend (`stub` or the index version), deadline table
   source, n. A report sentence with a number names its condition when it is not the real system ("with the
   stub search").
4. **One written rule, one place.** Labelling rules live in `eval/testsets/README.md`, interfaces in
   `docs/STATUS.md`, decisions here. A commit that changes behaviour updates the written rule in the same commit.
5. **Built means measured, or said why not.** A new output field or feature comes with a test case that grades it,
   or a line in the component table of `docs/architecture.md`: "not measured, because …".
6. **A deadline you will miss is announced before it passes**, with the new date (team agreement §5: missing it
   without telling the team is what counts as not delivering). The evaluation and safety lead checks the
   next-actions table of `docs/STATUS.md` every evening and asks about rows past their date.

**Consequences.**

- The week-2 report treats all 42 cases as the development set: it gives accuracy for `seen` and `new` separately but does not call `new` unseen, and says why (gap 1).
- A held-out set of 10–15 cases (`heldout_v1`) is written by Sun 22 18:00; its sha256 is committed first, and it is first run on the best week-2 prompt.
- Before the W2.5 runs, the agent and tools lead writes the plan rows: which prompt is "the main prompt" and the one change of v2 and of v3.
- Gap 3 becomes a measurement in week 3: the same 42 cases with the stub and with the real search; every case that passes with the stub and fails with real search is a retrieval failure (W3.8).
- `urgency` gets graded cases or the "not measured" line (gap 5).
- Unit tests in `tests/test_dates.py`, `test_agent.py` and `test_classifier.py` also take their expected values from `week2_cases.jsonl` (written before this decision). They stay as regression tests; no new test is derived from a test set, and no test reads a held-out file.

## D-008 — Corpus scale: at least 10,000 chunks (proposed, 2026-11-18; owner: data and retrieval lead)

**Context.** The instructor asked for a corpus of at least 10,000 chunks (2026-11-18). The 48 documents of D-005 give
a few hundred.

**Decision.** Two layers.

| Layer | What | Reviewed | Where |
|---|---|---|---|
| Core | The 48 documents of D-005: every fact the test sets depend on, the planned confusers, the regulation, the calendar | Every document, by hand | `data/corpus/` |
| Bulk | Fictional courses across many departments: syllabi with revised versions, and course announcements, assembled by a seeded generator from a pool of hand-reviewed section texts with randomized values (penalties, dates, attendance rules, instructors) | The section pool by hand; a random sample of generated documents | `scripts/generate_bulk_corpus.py` → `data/corpus_bulk/` |

Rules: the bulk generator never produces a core course code (CS-301, CS-310, CS-130, MATH-212, MATH-221,
ECON-101, AIC-390), so no generated text contradicts a test fact; it never produces dormitory, tuition or fee
content, so w1-20 stays unanswerable. Syllabi are `audience: all`, announcements `enrolled:<course>`. The count is
reached by adding documents, not by shrinking chunks: chunk size is chosen on its own merits (W3.2).

**Why.** A realistic university has hundreds of syllabi with the same structure and near-identical policy
sections that differ only in numbers. That is where dense search confuses courses and where BM25, metadata and
the reranker earn their place, so the ablations (W3.7) measure something real. Writing or reviewing thousands of
documents by hand in a week is impossible; a seeded generator is reproducible (R8) and costs no API calls.

**Consequences.** Retrieval is evaluated without the course filter as the main configuration (the question
alone), and with it as an extra row, so the filter cannot hide the scale. Index build time grows (embedding
10,000 chunks; slow on CPU). The bulk is visibly templated; the report says so in its limitations.

## D-007 — Retrieval stack: in-memory hybrid search with a local reranker (proposed, 2026-11-18; owner: data and retrieval lead)

**Decision.** No database for retrieval. Chunks live in `data/chunks.jsonl`; indexes are built by a script and
cached locally (not committed).

| Part | Choice |
|---|---|
| Keyword search | BM25 with `bm25s` |
| Dense search | `BAAI/bge-m3` through `sentence-transformers`, normalized vectors, cosine in numpy |
| Fusion | Reciprocal rank fusion, k = 60, over the top 20 of each |
| Reranker | `BAAI/bge-reranker-v2-m3` cross-encoder on the fused top 20 |
| Gold unit for evaluation | Document and section (`doc_id`, `section`), not chunk id |

**Why.** About 10,000 chunks (D-008) × 1,024 dimensions is about 40 MB of float32: brute-force cosine in numpy is
fast at this size, so a vector database adds setup (R19) and no measurable benefit. The corpus mixes Turkish and English, so both models are multilingual. Exact identifiers (CS-301 /
CS-310, "Article 12") are what BM25 handles and embeddings handle badly (handbook, ingredient 7), so hybrid
search is the default and dense-only is an ablation. Embedding and reranking run locally, so retrieval evaluation
(W3.5) and both ablations (W3.7) cost no API calls and do not compete with the Groq limits (D-006). Gold passages
are set at section level so that a change in chunk size does not invalidate the retrieval test set (R9).

**Consequences.** The first index build downloads the two models (a few GB) and is slow on CPU; results record
the model ids and revisions. Turkish casing needs explicit normalization (`İ`/`ı`) before BM25 tokenization.
Replaces the PostgreSQL + pgvector idea from proposal slide 4 and closes the open item in D-005.

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

## D-005 — Response to the RAG feedback (accepted, 2026-11-18; owner: data and retrieval lead)

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
Closed by D-007 (2026-11-18). Accepted on 2026-11-18: the instructor asked for RAG in next week's live demo
(`docs/feedback/2026-11-18-week1.md`).

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
