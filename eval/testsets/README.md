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
| `deadlines[]` | deadline_message, lookup, reminder: `course`, `item`, `item_key`, `due_date`, `due_time`, `due_candidates[]`, `status` (`new`, `updated`, `unverified`), `supersedes` (old date and time, or null) | the set must match exactly (no missing, no extra rows); rows match on `(course, item_key)`, then every field exact |
| `ask_user` | an input with two readings consistent with the whole message, **and** the two readings give different answers (see Dates below) | exact |
| `abstain` | always | exact |
| `sources[]` | `{doc_id, section}` | every expected source must be cited; extra sources are allowed and counted |
| `must_include[]`, `must_not[]` | answers in prose | LLM judge (W2.6) |
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

## Known issues in `week1_inputs.jsonl` (frozen; fix in the week-2 set)

| Input | Issue | Fix in the next version |
|---|---|---|
| w1-17 | Expected reminder time 09:00 follows no stated rule; "one day before" a 23:59 deadline reads as 2026-11-22 23:59 | State the rule in `expected`, or use the deadline time minus 24 h |
| w1-15 | Expected HW3 (2026-12-04 23:59) appears in no message; the answer depends on the database seed | Seed row listed in `docs/data_inventory.md` §2 |
| all | 3 unanswerable and 2 adversarial cases; W2.3 needs at least 40 cases with at least 5 unanswerable, 5 adversarial and 5 edge cases | Week-2 set |
| all | Every label is by one person (evaluation lead); no second rater yet | 20 cases labelled blind by a second member, Cohen's κ (W2.6) |
