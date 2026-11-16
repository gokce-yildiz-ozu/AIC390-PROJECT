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

<!-- Proposal slide 4: one write tool, sandboxed, confirmation required. -->

| Tool | Input | Output | Type · risk |
|---|---|---|---|
| `list_obligations` | TODO | TODO | Read · low |
| `days_until` | TODO | TODO | Read · low (date math in code) |
| `search_policies` | TODO | TODO | Read · low |
| `read_new_emails` | TODO | TODO | Read · medium (untrusted) |
| `create_calendar_event` | TODO | Preview; writes to the sandbox calendar only after the user confirms | Write · high |

## 4. Sources of untrusted input

| Source | Example risk | Test input |
|---|---|---|
| Inbox emails | Instruction hidden in an email body | w1-24 |
| LMS posts, forum | A student posing as the instructor | w1-25 |
| TODO | | |

Trust decisions use the `sender` field from channel metadata, never claims inside the text
(`eval/testsets/README.md`).
