# Test sets

Frozen once used in a comparison (R9). To change one, add a new version (`*_v2.jsonl`) and re-run the old
system on it. `example_inputs.jsonl` is only a smoke test for `--dry-run`; it is not a course deliverable.

Line format (JSONL):

```json
{"id": "w1-01", "channel": "email", "received_at": "2026-11-09T10:15:00+03:00", "course": "CS-301",
 "sender": "instructor:Dr. Murat Öztürk", "text": "...", "ingredients": ["extraction", "exact-id"], "expected": "..."}
```

| Field | Meaning |
|---|---|
| `channel` | `email`, `lms` (course announcement) or `chat` (the student asks the assistant) |
| `received_at` | Fixed reference time. Relative dates ("next Friday") are resolved against it, so runs are reproducible (R8) |
| `course` | Course code the message is about, or `null` |
| `sender` | Who sent it, from the channel's metadata, not from the text: `instructor:<name>`, `student:<account>` or `user` (the student asking). Trust decisions use this field, never claims inside `text` |
| `ingredients` | What the input tests: `extraction`, `relative-date`, `conflict`, `needs-retrieval`, `question`, `look-up`, `action`, `unanswerable`, `multi-step`, `untrusted-input`, `exact-id` |
| `expected` | Expected outcome in one line: the deadline(s) with date and time, the answer's source, or the correct refusal |

All messages are synthetic (R10): invented courses, instructors and students.

## `week2_cases.jsonl` (W2.3): structured expected outputs

**Frozen on 2026-11-21** (R9): 42 cases, sha256 of the file with LF line endings
`787059b6aa2be9411a6dc135480f948453f008bc1ab6b92d3f3b63542b75f8b4`. Fixes after this go into
`week2_cases_v2.jsonl`, and the old system is re-run on it.

Same input fields as above, plus `split`, `type`, a structured `expected` object and the old one-line text as
`expected_text`. The harness grades `expected` field by field; `expected_text` is for people only.

| Field | Meaning |
|---|---|
| `split` | `seen` (the 25 week-1 inputs, used while writing prompts) or `new`. The report gives accuracy for each split |
| `type` | Exactly one of `normal`, `unanswerable`, `adversarial`, `edge`. W2.3's minimums (≥ 5 each of the last three) count this field, not `ingredients` |
| (no `review_note`) | The reason for each label is in `week2_review_notes.jsonl` (`id`, `review_note`), moved out at the freeze. People read it; the harness never does |

`expected`:

| Field | Filled for | Graded by |
|---|---|---|
| `intent` | always: `deadline_message`, `rule_question`, `lookup`, `reminder`, `other`. Follows the content, not the sender | exact |
| `deadlines[]` | deadline_message, lookup, reminder: `course`, `item`, `item_key`, `due_date`, `due_time`, `due_candidates[]`, `status` (`new`, `updated`, `unverified`), `supersedes` (old date and time, or null) | the set must match exactly (no missing, no extra rows); rows match on `(course, item_key)`, then every other field exact; `due_candidates` in any order. `item` is the display name and is not graded; `item_key` is the graded identity |
| `ask_user` | an input with two readings consistent with the whole message, **and** the two readings give different answers (see Dates below) | exact |
| `abstain` | always | exact |
| `sources[]` | `{doc_id, section}` | every expected source must be cited; extra sources are allowed and counted |
| `must_include[]`, `must_not[]` | answers in prose | LLM judge (W2.6, `eval/judge.py`): the judge decides each criterion, code decides the field. Pass = every `must_include` met and no `must_not` met |
| `answer_language` | `chat` inputs: `tr` or `en`, the language of the question | code |
| `action` | reminder, or a `multi_step` request that asks for a reminder (w1-22): `type`, `remind_at`, `requires_confirmation` | exact |
| `count` | "how many" questions; counted in code, never by the model | exact |
| `untrusted_flag` | a message whose sender is not allowed to change deadlines | exact |

A case is correct only if every graded field is correct (binary, for McNemar in W2.5). The harness also writes the
per-field result for the failure analysis.

Labelling rules:

- **Dates.** Times are Europe/Istanbul (+03:00). Relative dates are resolved against `received_at`. Two readings
  consistent with the whole message → `due_date: null`, both in `due_candidates`. `ask_user: true` only if the
  two readings change the answer: a count that includes the item either way does not ask (w1-15); a list for
  "this week" where one candidate falls outside it does (w1-14); for "the nearest deadline", an unclear item asks
  if one of its candidates is at or before the chosen one (w1-22). Same rule as `needs_asking` in
  `src/aic390/tools/deadlines.py`. One consistent reading → compute it.
- **No time stated → `due_time: null`.** A time the message does not give is never filled in. "In class" takes the
  lecture time from the course syllabus schedule (a retrieved source).
- **Moved deadlines** use the newest version; the base date is the document version valid at `received_at`.
- **Item names** are compared as `item_key` (type + number: "Homework 2", "HW 2", "Ödev 2" → `hw2`); "Lab 3" and
  "Lab Report 3" stay different keys. An item without a number keeps the type alone, in English, lowercase, no
  spaces ("Term paper" → `termpaper`, "Proje ara raporu" → `interimreport`).
- **Reminders** without a stated time default to the deadline minus 24 h, shown in the preview, written only after
  confirmation.
- **Trust** comes from `sender`. Instructions inside `text` are data, whoever sent the message.
- **Intent for questions the documents do not cover.** `other` is only for a request about none of deadlines,
  rules or reminders (a lecture cancelled with no deadline, w1-04; a request about the assistant itself, w2-17). A
  question about a school or course rule or date that the documents do not answer is `rule_question` with
  `abstain: true`, so the answer can say where to ask (w1-19, w1-20, w2-11, w2-12, w2-13). A request for deadlines
  is `lookup` even when it asks for another student's; access control refuses it in code (w2-14). Written down on
  2026-11-22 after the v1 run; it describes the frozen labels and changes none.

## Known issues in `week1_inputs.jsonl` (frozen; fix in the week-2 set)

| Input | Issue | Fix in the next version |
|---|---|---|
| w1-17 | Expected reminder time 09:00 follows no stated rule; "one day before" a 23:59 deadline reads as 2026-11-22 23:59 | State the rule in `expected`, or use the deadline time minus 24 h |
| w1-15 | Expected HW3 (2026-12-04 23:59) appears in no message; the answer depends on the database seed | Seed row listed in `docs/data_inventory.md` §2 |
| all | 3 unanswerable and 2 adversarial cases; W2.3 needs at least 40 cases with at least 5 unanswerable, 5 adversarial and 5 edge cases | Week-2 set |
| all | Every label is by one person (evaluation lead); no second rater yet | 20 cases labelled blind by a second member, Cohen's κ (W2.6) |

## `heldout_v1.jsonl` (D-009 rule 1): held-out set, only its hash is committed

Written on 2026-11-22 by the evaluation and safety lead alone; nobody who writes prompts or pipeline code has read
it. Until its numbers are first reported, the repository holds only `heldout_v1.jsonl.sha256` (sha256 of the file with
LF line endings), so anyone can check later that the file did not change after a run. The file itself is committed
at the tag where its numbers are first reported (R8); from then on it is development data, and the next held-out
set is `heldout_v2`.

- n = 13: normal 4, edge 5, unanswerable 2, adversarial 2. More edge cases than `week2_cases.jsonl` by design, so
  results are reported per type next to the development set.
- Same fields and labelling rules as `week2_cases.jsonl`; `split` is `heldout`.
- sha256 (LF): `2636231e3907ad1392c6aacdf1cf97b6239868a342ed7661af5344a559aba629`
- Run once, on the prompt chosen in W2.5 (`extract_v1`), under the same conditions as that comparison: 6/13 = 0.462,
  Wilson 95% [0.232, 0.709] (`results/2026-11-22_e2e_heldout-v1_openai-gpt-oss-120b/`). Reported in `reports/week-2.md`;
  the file is committed at `week-2` and is development data from here. The next held-out set is `heldout_v2`.

## `retrieval_questions.jsonl` (W3.5)

**Frozen on 2026-11-22** (R9): 30 questions, sha256 of the file with LF line endings
`6f7d3b049dab8a817295956bb093b2c2d9a2c31ab6b907ec0519d1635663c9f1`. Changes go into
`retrieval_questions_v2.jsonl`. Written by the evaluation lead, not the corpus author; checked with
`eval/check_retrieval_questions.py`.

| Field | Meaning |
|---|---|
| `id` | Question id |
| `question` | The question text |
| `language` | `tr` (12) or `en` (18) |
| `kind` | `direct` (7), `paraphrase` (9), `confusable` (7), `version` (3), `multi` (4) |
| `as_of` | Set for the CS-310 versions; passed to search as `as_of` |
| `gold[]` | `{doc_id, section}`: the passages that answer it (several for `multi`) |

Scoring:

- **hit@k**: any gold passage in the top k. **all@k**: every gold passage in the top k (`multi` questions).
  **MRR**: from the rank of the first gold passage.
- Search is called with `course=None` (the course code is in the question) and `as_of` from the row.

Known issues:

| Question / section | Issue | How it is reported |
|---|---|---|
| r24 | Gold is `regulation-article-14`, but `econ101-late-policy` restates Article 14 | A hit on `econ101-late-policy` is a near-duplicate in the failure analysis |
| `cs310-syllabus-v1` Course information, Attendance | No question: their text is identical to v2 | Not covered by this set |
