# Data inventory (W1.4)

Owners: data and retrieval lead (documents, database), agent and tools lead (action API, tools).
Facts below come from the proposal (`docs/proposal/`) and D-005. All data is synthetic (R10).
Replace every `TODO`; delete the hints when done.

## 1. Documents (for RAG)

<!-- Proposal: 28 synthetic documents. D-005 (proposed) raises this to 45–60 because W3.1 needs ≥ 30 and the
instructor found the RAG too easy. Decide the final count here and record it in D-005. -->

| Type | Count (planned) | Example | Why it makes retrieval harder |
|---|---|---|---|
| Course syllabi | TODO | CS-301 syllabus (late policy, grading) | Confusable course codes (CS-301 vs CS-310) |
| Revised syllabus versions | TODO | CS-310 syllabus v2 | Same course, different dates by version |
| Course policies | TODO | ECON-101 late-work policy | Overrides the regulation |
| Regulation, split by article | TODO | Article 9 (withdrawal), 12 (make-up), 14 (late work) | Exact identifiers ("Article 12") |
| Academic calendar | TODO | Make-up week, last withdrawal day | Dates referenced indirectly |
| FAQ | TODO | | |

Metadata per chunk (D-005): course, doc type, version, valid from, language, audience. TODO: confirm.

## 2. Database tables

| Table | Columns | Notes |
|---|---|---|
| `deadlines` | TODO (proposal: title, type, course, due, source, evidence quote, verified) | Counting and listing go to SQL, never to RAG |
| `courses` | TODO | |
| `enrolments` | TODO | Which student takes which course; tools return only that student's rows |

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
| TODO | | |

Trust decisions use the `sender` field from channel metadata, never claims inside the text
(`eval/testsets/README.md`).
