# Data inventory (W1.4)

Owners: data and retrieval lead (documents, database), agent and tools lead (action API, tools).
Facts below come from the proposal (`docs/proposal/`) and D-005. All data is synthetic (R10).

## 1. Documents (for RAG)

**Update 2026-11-23:** built as 10 core documents (`data/corpus/`) plus 3,879 generated documents (`data/corpus_bulk/`), 11,388 chunks (D-008). The 48-document plan below is the week-1 plan.

48 synthetic documents (D-005): above W3.1's minimum of 30, and built so that a course code alone does not
identify the right passage.

| Type | Count (planned) | Example | Why it makes retrieval harder |
|---|---|---|---|
| Course syllabi | 6 | CS-301, CS-310, CS-130, MATH-212, MATH-221, ECON-101 | Confusable course codes (CS-301 / CS-310 / CS-130, MATH-212 / MATH-221) |
| Revised syllabus versions | 4 | CS-310 syllabus v2 | Same course, different dates by version; only the newest valid version counts |
| Course policies | 8 | ECON-101 late-work policy | Overrides the regulation |
| Regulation, split by article | 16 | Article 9 (withdrawal), 12 (make-up), 14 (late work) | Exact identifiers ("Article 12"); similar wording across articles |
| Academic calendar | 3 | Fall term calendar, make-up week, final exam period | Dates referenced indirectly ("before the make-up week") |
| Past course announcements | 6 | CS-301 office hours moved | Near-duplicates of real deadlines act as distractors |
| FAQ | 5 | Withdrawal, make-up exams, LMS submission | Generic answers compete with course-specific ones |
| **Total** | **48** | | |

**Facts the corpus must contain** (from the expected outputs in `eval/testsets/week2_cases.jsonl`). The `doc_id`
and `section` columns are the gold sources of the test sets: a file or heading named differently fails those cases.

| Fact | `doc_id` | `section` | Cases |
|---|---|---|---|
| Late penalty 10% per day, at most 3 days, then 0 | `cs301-syllabus` | Late policy | w1-09, w2-02 (confuser) |
| Homework 3 due 2026-12-04 23:59 (same as the seed row in §2) | `cs301-syllabus` | Schedule | w2-01 |
| Lab attendance of at least 70% is mandatory (same text in v1 and v2) | `cs310-syllabus-v2` | Attendance | w1-13, w2-12 (confuser) |
| Late penalty 5% per day, at most 5 days, then 0 (same text in v1 and v2; deliberately different from CS-301) | `cs310-syllabus-v2` | Late policy | w2-02 |
| v1, valid from the start of term: Lab 3 due 2026-11-06 23:59 | `cs310-syllabus-v1` | Schedule | w1-06 (outdated version, must not be the base) |
| v2, valid from 2026-11-02: Lab 3 due 2026-11-13 23:59. Lab 4 is either not listed or due 2026-11-27 23:59 | `cs310-syllabus-v2` | Schedule | w1-06, w1-24 |
| MATH-212 lectures: Tuesday and Thursday, 10:40–12:30 | `math212-syllabus` | Schedule | w1-03, w2-15 |
| Make-up week starts 2026-11-30 | `academic-calendar-fall-2026` | Make-up week | w1-08 |
| Last day to withdraw: 2026-12-04 | `academic-calendar-fall-2026` | Withdrawal | w1-10, w2-03 |
| Withdrawal rule; the date is not in the article, it points to the calendar | `regulation-article-9` | Article 9 | w1-10, w2-03 |
| Make-up exam: documented excuse, handed in within 3 working days | `regulation-article-12` | Article 12 | w1-11 |
| The course instructor sets the late-work rule | `regulation-article-14` | Article 14 | w1-12, w1-21 |
| ECON-101 does not accept late work | `econ101-late-policy` | Late work | w1-12, w1-22 |

**Naming rules** (fill a gap in interface 3; proposed 2026-11-19, data and retrieval lead to confirm):

- `doc_id` is the file name without `.md`, lowercase, words joined by hyphens. Course documents start with the
  course code without its hyphen (`cs301-syllabus`, `econ101-late-policy`); each regulation article is its own
  document (`regulation-article-12`).
- A document with more than one version gets `-v<N>` on every version, v1 included; front matter `version` and
  `valid_from` match. Among the documents the test sets cite, only the CS-310 syllabus has versions. Versioning
  another cited document changes gold sources: tell the evaluation and safety lead first.
- `section` is the text of the `##` heading. The harness compares it after trimming and lowercasing, nothing more.

**Deliberately not in the corpus** (each one keeps an unanswerable case unanswerable):

| Not anywhere in the corpus | Case |
|---|---|
| Dormitory, tuition and fee documents | w1-20, w2-11 |
| An attendance rule for CS-130, in its syllabus or in any regulation article | w2-12 |
| Curving or grade adjustment in MATH-212 | w2-13 |

**Metadata per chunk:** `doc_id`, `course` (or null), `doc_type`, `section` (article or heading, used in
citations), `version`, `valid_from`, `language` (tr / en), `audience` (all students, or students enrolled in the
course; W3.1 "who may see it").

## 2. Database tables

| Table | Columns | Notes |
|---|---|---|
| `students` | `student_id`, `name` (synthetic), `program` | The student comes from the session, never from the model |
| `courses` | `course_code`, `title`, `instructor`, `term`, `language` | |
| `enrolments` | `student_id`, `course_code`, `term` | Tools return only the session student's courses |
| `messages` | `message_id`, `student_id`, `channel` (email, lms), `sender`, `course_code`, `received_at`, `subject`, `body` | Sandbox inbox read by `read_new_emails`; `body` is untrusted; `received_at` resolves relative dates |
| `deadlines` | `deadline_id`, `student_id`, `course_code`, `title`, `type` (homework, lab, quiz, exam, project, other), `due_date`, `due_time` (null if not stated), `source_id`, `evidence_quote`, `verified`, `supersedes_id`, `created_at` | Counting and listing go to SQL, never to RAG. A moved deadline is a new row that points to the old one, so both sources can be cited |
| `calendar_events` | `event_id`, `student_id`, `deadline_id`, `title`, `start_at`, `status` (pending, confirmed) | Sandbox write target of `create_calendar_event` |


**Seed rows the week-1 expected outputs need.** Look-up and action inputs (w1-14 to w1-22) are answered from the
`deadlines` table as it stands at their `received_at` (also w2-05 to w2-07), so the seed must contain the deadlines from the earlier
messages (w1-01 to w1-08, including moved dates as `supersedes_id` rows) plus one deadline that appears in no message:

| Row | Course | Due | Needed by |
|---|---|---|---|
| HW3 | CS-301 | 2026-12-04 23:59 | w1-15 ("3 submissions left") |

The student in the seed is enrolled in CS-301, CS-310, MATH-212, ECON-101 and AIC 390 (persona in
`docs/use_case_brief.md`).

## 3. Action API sketch

Owner: agent and tools lead. A sketch for week 1; the tools are built in week 4 (W4.1) and exposed through MCP in
week 5 (W5.1). Four read tools and one write tool. No tool can send email, delete data or make payments.

| Tool | Input | Output | Type · risk |
|---|---|---|---|
| `list_obligations` | `from_date`, `to_date`, optional `course`, optional `type` (homework, exam, project…) | Deadlines in the range from the `deadlines` table, newest version only: title, course, due, source, verified | Read · low |
| `days_until` | `due` (date and time) | Days and hours left, computed in code in Europe/Istanbul time | Read · low (date math in code) |
| `search_policies` | `query`, optional `course`, optional `doc_type` | Top 5 passages, each with document, version and section, for numbered citations; empty if nothing matches | Read · low |
| `read_new_emails` | `since` (date and time) | New messages from the sandbox inbox, each with `sender` from channel metadata; the body is marked as untrusted data | Read · medium (untrusted) |
| `create_calendar_event` | `title`, `start`, optional `deadline_id` | Step 1 returns a preview and `pending_confirmation`; step 2 writes to the sandbox calendar only after the user presses Confirm | Write · high |

Rules for every tool:

- **Same result shape.** Every tool returns `ok`, `data` and `error`. Errors say what to do next, for example
  "course CS-999 not found; known courses: CS-301, MATH-212, ECON-101".
- **The student comes from the session, not from the model.** No tool takes a `student_id` argument; tools return
  only the logged-in student's rows, so a message cannot ask for someone else's data.
- **Counting and dates in code.** "What's due this week?" is a `list_obligations` query and "2 hours before" is
  computed in code, never by the model.
- **Writes are two steps.** The model can only ask for a preview; the confirmation comes from the user, not from the
  model (example: w1-17, a reminder one day before CS-301 HW2).

## 4. Sources of untrusted input

| Source | Example risk | Test input |
|---|---|---|
| Inbox emails | Instruction hidden in an email body | w1-24 |
| LMS posts, forum | A student posing as the instructor | w1-25 |
| Retrieved documents (syllabus, announcement text) | An instruction hidden in a passage that RAG puts into the prompt | none yet (W2.8, W5.5) |
| Rows extracted into `deadlines` | A fake deadline from a malicious message later treated as fact (second-order injection) | w1-24, w1-25 |

Trust decisions use the `sender` field from channel metadata, never claims inside the text
(`eval/testsets/README.md`).
